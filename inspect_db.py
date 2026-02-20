import os
from notion_client import Client

notion = Client(auth=os.getenv("NOTION_TOKEN"))

DB_ID = "2c6bba394fae80d392bedbb0c3df36e1"  # Reenrollment DB

db = notion.databases.retrieve(database_id=DB_ID)

print("Database title:", "".join(t.get("plain_text", "") for t in db.get("title", [])))
print("Database keys:", list(db.keys()))
print("Database properties count:", len(db.get("properties", {})))

data_sources = db.get("data_sources", [])
print("\nData sources count:", len(data_sources))
print("Data sources:", [ds.get("id") for ds in data_sources])

if not data_sources:
    print("\nNo data_sources found on this database object.")
    raise SystemExit(0)

ds_id = data_sources[0]["id"]

# Retrieve schema from data source (newer Notion API model)
ds = notion.data_sources.retrieve(data_source_id=ds_id)

print("\nDATA SOURCE ID:", ds_id)
print("Data source properties count:", len(ds.get("properties", {})))
print("\nData source properties:")

for name, meta in ds.get("properties", {}).items():
    print("-", name, ":", meta.get("type"))