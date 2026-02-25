import os
from collections import Counter, defaultdict
from notion_client import Client

notion = Client(auth=os.getenv("NOTION_TOKEN"))

DATABASE_ID = "2c6bba394fae802cb4dbc8db3ddc1ea6"

# Get data source id (new Notion API)
db = notion.databases.retrieve(database_id=DATABASE_ID)
data_sources = db.get("data_sources", [])
if not data_sources:
    raise RuntimeError("No data_sources found. Make sure the integration is shared.")

DATA_SOURCE_ID = data_sources[0]["id"]

def get_title(props):
    # Find title property (Student Name)
    for _, v in props.items():
        if v.get("type") == "title":
            title = v.get("title", [])
            return "".join(t.get("plain_text", "") for t in title) if title else "(blank name)"
    return "(no title)"

def get_select(props, prop_name):
    p = props.get(prop_name)
    if not p:
        return None
    if p["type"] == "select":
        return p["select"]["name"] if p["select"] else None
    return None

def get_people(props, prop_name):
    p = props.get(prop_name)
    if not p:
        return []
    if p["type"] == "people":
        return [person.get("name", "(no name)") for person in (p["people"] or [])]
    return []

def get_rich_text(props, prop_name):
    p = props.get(prop_name)
    if not p:
        return None
    if p["type"] == "rich_text":
        rt = p["rich_text"] or []
        return "".join(x.get("plain_text", "") for x in rt).strip() if rt else None
    return None

def fetch_all_pages():
    results = []
    cursor = None
    while True:
        payload = {"data_source_id": DATA_SOURCE_ID, "page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        resp = notion.data_sources.query(**payload)
        results.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results

pages = fetch_all_pages()
print(f"\nENROLLMENT HEALTH REPORT (v1)\nTotal records pulled: {len(pages)}\n")

stage_counts = Counter()
owner_counts = Counter()

missing_owner = []
missing_next_step = []
missing_stage = []

stage_to_names = defaultdict(list)

def get_multiselect_names(props, prop_name):
    p = props.get(prop_name)
    if not p:
        return []
    if p.get("type") == "multi_select":
        return [x.get("name") for x in (p.get("multi_select") or [])]
    return []

for page in pages:
    props = page.get("properties", {})

    name = get_title(props)

    stage = get_select(props, "Pipeline Stage")
    if not stage:
        missing_stage.append(name)
        stage = "(No Pipeline Stage)"
    stage_counts[stage] += 1
    stage_to_names[stage].append(name)

    owners = get_multiselect_names(props, "Assigned Staff")
    if not owners:
        missing_owner.append(name)
    else:
        for owner in owners:
            owner_counts[owner] += 1

    next_step = get_rich_text(props, "Next Step")
    if not next_step:
        missing_next_step.append(name)

# Print stage summary
print("1) Prospects by Pipeline Stage")
for stage, count in stage_counts.most_common():
    print(f"   - {stage}: {count}")

print("\n2) Accountability / hygiene issues")
print(f"   - Missing Assigned Staff: {len(missing_owner)}")
print(f"   - Missing Next Step: {len(missing_next_step)}")
print(f"   - Missing Pipeline Stage: {len(missing_stage)}")

# Print top owners
print("\n3) Prospects by Assigned Staff (top)")
for owner, count in owner_counts.most_common(15):
    print(f"   - {owner}: {count}")

# Show samples so you can act immediately
def show_sample(title, arr, n=10):
    print(f"\n{title} (showing up to {n})")
    for x in arr[:n]:
        print("   -", x)

show_sample("Missing Assigned Staff", missing_owner)
show_sample("Missing Next Step", missing_next_step)
show_sample("Missing Pipeline Stage", missing_stage)

print("\nDone.\n")






