import config
from notion_io import fetch_all_pages_from_databases, get_notion_client
from report import analyze_pages, export_csvs, print_report

# ---------------------------
# LOAD
# ---------------------------
notion = get_notion_client()
pages = fetch_all_pages_from_databases(notion, config.DATABASES)

print(f"\nENROLLMENT HEALTH REPORT (v2)\nTotal records pulled: {len(pages)}\n")


# ---------------------------
# ANALYZE
# ---------------------------
results = analyze_pages(pages, config)


# ---------------------------
# PRINT REPORT
# ---------------------------
print_report(results, config)


# ---------------------------
# EXPORT CSVs
# ---------------------------
export_csvs(results, len(pages), config)

print(f"Exported:\n - {config.SUMMARY_CSV}\n - {config.ACTIONS_CSV}")
