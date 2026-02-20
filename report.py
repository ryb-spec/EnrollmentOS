import csv
from collections import Counter, defaultdict

from extractors import (
    days_since,
    get_multiselect_names,
    get_rich_text,
    get_stage_value,
    get_title,
    owners_str,
)


def analyze_pages(pages, config):
    stage_counts = Counter()
    owner_counts = Counter()

    missing_owner = []
    missing_next_step = []
    missing_stage = []

    # owner_actions[owner]["stale"|"missing_next_step"|"missing_stage"] -> list of items
    owner_actions = defaultdict(lambda: {"stale": [], "missing_next_step": [], "missing_stage": []})

    stale_items = []
    action_rows = []

    for page in pages:
        props = page.get("properties", {})
        name = get_title(props)
        url = page.get("url", "")
        source = page.get("_source", "(unknown)")

        stage = get_stage_value(props, config.PROP_STAGE)
        if not stage:
            stage = f"(No {config.PROP_STAGE})"
            missing_stage.append(name)

        stage_counts[stage] += 1

        owners = get_multiselect_names(props, config.PROP_ASSIGNED)
        if owners:
            for o in owners:
                owner_counts[o] += 1
        else:
            missing_owner.append(name)

        next_step = get_rich_text(props, config.PROP_NEXT_STEP)
        if not next_step:
            missing_next_step.append(name)

        last_edited_time = page.get("last_edited_time", "")
        days_stale = days_since(last_edited_time) if last_edited_time else None

        is_stale = (
            days_stale is not None
            and days_stale >= config.STALE_DAYS
            and stage not in config.EXCLUDE_STALE_STAGES
        )

        # --- STALE ---
        if is_stale:
            item = {
                "name": name,
                "stage": stage,
                "owners": owners_str(owners),
                "days_stale": days_stale,
                "last_edited_time": last_edited_time,
                "url": url,
            }
            stale_items.append(item)

            if owners:
                for o in owners:
                    owner_actions[o]["stale"].append(item)
            else:
                owner_actions["(unassigned)"]["stale"].append(item)

            action_rows.append({
                "name": name,
                "stage": stage,
                "owners": owners_str(owners),
                "source": source,
                "issue_type": "STALE",
                "days_stale": days_stale,
                "last_edited_time": last_edited_time,
                "url": url,
            })

        # --- MISSING NEXT STEP ---
        if not next_step:
            if owners:
                for o in owners:
                    owner_actions[o]["missing_next_step"].append({"name": name, "stage": stage, "url": url})
            else:
                owner_actions["(unassigned)"]["missing_next_step"].append({"name": name, "stage": stage, "url": url})

            action_rows.append({
                "name": name,
                "stage": stage,
                "owners": owners_str(owners),
                "source": source,
                "issue_type": "MISSING_NEXT_STEP",
                "days_stale": days_stale if days_stale is not None else "",
                "last_edited_time": last_edited_time,
                "url": url,
            })

        # --- MISSING STAGE ---
        if stage == f"(No {config.PROP_STAGE})":
            if owners:
                for o in owners:
                    owner_actions[o]["missing_stage"].append({"name": name, "stage": stage, "url": url})
            else:
                owner_actions["(unassigned)"]["missing_stage"].append({"name": name, "stage": stage, "url": url})

            action_rows.append({
                "name": name,
                "stage": stage,
                "owners": owners_str(owners),
                "source": source,
                "issue_type": f"MISSING_{config.PROP_STAGE.upper()}",
                "days_stale": days_stale if days_stale is not None else "",
                "last_edited_time": last_edited_time,
                "url": url,
            })

    return {
        "stage_counts": stage_counts,
        "owner_counts": owner_counts,
        "missing_owner": missing_owner,
        "missing_next_step": missing_next_step,
        "missing_stage": missing_stage,
        "owner_actions": owner_actions,
        "stale_items": stale_items,
        "action_rows": action_rows,
    }


def _show_sample(title, arr, n=10):
    print(f"\n{title} (showing up to {n})")
    for x in arr[:n]:
        print("   -", x)


def print_report(results, config):
    stage_counts = results["stage_counts"]
    owner_counts = results["owner_counts"]
    missing_owner = results["missing_owner"]
    missing_next_step = results["missing_next_step"]
    missing_stage = results["missing_stage"]
    owner_actions = results["owner_actions"]
    stale_items = results["stale_items"]

    print(f"1) Applications by {config.PROP_STAGE}")
    for stg, count in stage_counts.most_common():
        print(f"   - {stg}: {count}")

    print("\n2) Accountability / hygiene issues")
    print(f"   - Missing {config.PROP_ASSIGNED}: {len(missing_owner)}")
    print(f"   - Missing {config.PROP_NEXT_STEP}: {len(missing_next_step)}")
    print(f"   - Missing {config.PROP_STAGE}: {len(missing_stage)}")

    print(f"\n3) Applications by {config.PROP_ASSIGNED} (top)")
    for owner, count in owner_counts.most_common(30):
        print(f"   - {owner}: {count}")

    stale_items_sorted = sorted(stale_items, key=lambda x: x["days_stale"], reverse=True)
    print(f"\n4) Stale (>= {config.STALE_DAYS} days since last edit) excluding {config.EXCLUDE_STALE_STAGES}")
    if not stale_items_sorted:
        print("   - None")
    else:
        for item in stale_items_sorted[:25]:
            print(
                f"   - {item['name']} | {item['stage']} | {item['owners']} | "
                f"{item['days_stale']} days | {item['last_edited_time']}"
            )

    _show_sample(f"Missing {config.PROP_ASSIGNED}", missing_owner)
    _show_sample(f"Missing {config.PROP_NEXT_STEP}", missing_next_step)
    _show_sample(f"Missing {config.PROP_STAGE}", missing_stage)

    print("\n5) Owner Action Lists (counts)")
    for owner in sorted(owner_actions.keys()):
        a = owner_actions[owner]
        print(
            f"   - {owner}: stale={len(a['stale'])}, missing_next_step={len(a['missing_next_step'])}, "
            f"missing_{config.PROP_STAGE.lower()}={len(a['missing_stage'])}"
        )

    print("\nDone.\n")


def export_csvs(results, total_records, config):
    stage_counts = results["stage_counts"]
    owner_counts = results["owner_counts"]
    missing_owner = results["missing_owner"]
    missing_next_step = results["missing_next_step"]
    missing_stage = results["missing_stage"]
    action_rows = results["action_rows"]

    # Summary CSV
    with open(config.SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Metric", "Value"])
        w.writerow(["Total Records", total_records])
        w.writerow([f"Missing {config.PROP_ASSIGNED}", len(missing_owner)])
        w.writerow([f"Missing {config.PROP_NEXT_STEP}", len(missing_next_step)])
        w.writerow([f"Missing {config.PROP_STAGE}", len(missing_stage)])
        w.writerow(["Stale Threshold (days)", config.STALE_DAYS])
        w.writerow(["Excluded Stages", ", ".join(sorted(config.EXCLUDE_STALE_STAGES))])

        w.writerow([])
        w.writerow([config.PROP_STAGE, "Count"])
        for stg, count in stage_counts.most_common():
            w.writerow([stg, count])

        w.writerow([])
        w.writerow([config.PROP_ASSIGNED, "Count"])
        for owner, count in owner_counts.most_common():
            w.writerow([owner, count])

    # Actions CSV
    fields = ["name", "stage", "owners", "source", "issue_type", "days_stale", "last_edited_time", "url"]
    with open(config.ACTIONS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in action_rows:
            w.writerow(row)
