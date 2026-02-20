import os
from notion_client import Client


def get_notion_client():
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN env var not set. (Set it with setx NOTION_TOKEN \"...\")")
    return Client(auth=token)


def fetch_data_source_id(notion, database_id: str) -> str:
    db = notion.databases.retrieve(database_id=database_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise RuntimeError("No data_sources found. Make sure the database is shared with the integration.")
    return data_sources[0]["id"]


def fetch_all_pages(notion, data_source_id: str):
    results = []
    cursor = None
    while True:
        payload = {"data_source_id": data_source_id, "page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        resp = notion.data_sources.query(**payload)
        results.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def fetch_all_pages_from_databases(notion, databases):
    combined = []
    for label, db_id in databases:
        data_source_id = fetch_data_source_id(notion, db_id)
        pages = fetch_all_pages(notion, data_source_id)
        for page in pages:
            page["_source"] = label
        combined.extend(pages)
    return combined
