from datetime import datetime, timezone


def iso_to_dt(iso_str: str) -> datetime:
    # Notion uses Z for UTC; Python wants +00:00
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


def days_since(iso_str: str) -> int:
    dt = iso_to_dt(iso_str)
    return (datetime.now(timezone.utc) - dt).days


def get_title(props):
    # Find the title property (student name)
    for _, v in props.items():
        if v.get("type") == "title":
            title = v.get("title", [])
            return "".join(t.get("plain_text", "") for t in title) if title else "(blank name)"
    return "(no title)"


def get_rich_text(props, prop_name):
    p = props.get(prop_name)
    if not p:
        return None
    if p.get("type") == "rich_text":
        rt = p.get("rich_text") or []
        val = "".join(x.get("plain_text", "") for x in rt).strip()
        return val if val else None
    return None


def get_multiselect_names(props, prop_name):
    p = props.get(prop_name)
    if not p:
        return []
    if p.get("type") == "multi_select":
        return [x.get("name") for x in (p.get("multi_select") or []) if x.get("name")]
    return []


def get_stage_value(props, prop_name):
    """
    Notion databases can have a property literally named "Status" whose type is:
    - "select" (classic)
    - "status" (Notion's special status type)
    This function reads either.
    """
    p = props.get(prop_name)
    if not p:
        return None

    t = p.get("type")
    if t == "select":
        return p["select"]["name"] if p.get("select") else None
    if t == "status":
        return p["status"]["name"] if p.get("status") else None

    # If it's something unexpected, return None so it shows as missing
    return None


def owners_str(owners):
    return ", ".join(owners) if owners else "(unassigned)"
