import csv
import io
import re
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


SPREADSHEET_ID_PATTERN = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def _norm(v):
    return (v or "").strip().lower()


def _emails_for_props(props, config):
    emails = []
    for prop_name in [config.PROP_STUDENT_EMAIL, config.PROP_STUDENT_ALT_EMAIL]:
        p = props.get(prop_name)
        if not p:
            continue
        t = p.get("type")
        if t == "email":
            val = p.get("email")
            if val:
                emails.append(_norm(val))
        elif t == "rich_text":
            val = "".join(x.get("plain_text", "") for x in (p.get("rich_text") or []))
            if val:
                emails.append(_norm(val))
    return [e for e in emails if e]


def _latest_timestamp(a, b, timestamp_column):
    if not a:
        return b
    if not b:
        return a
    return a if str(a.get(timestamp_column, "")) >= str(b.get(timestamp_column, "")) else b


def _build_index(rows, config):
    by_email = {}
    by_name = {}
    for row in rows:
        email = _norm(row.get(config.GOOGLE_FORM_EMAIL_COLUMN, ""))
        name = _norm(row.get(config.GOOGLE_FORM_NAME_COLUMN, ""))
        if email:
            by_email[email] = _latest_timestamp(by_email.get(email), row, config.GOOGLE_FORM_TIMESTAMP_COLUMN)
        if name:
            by_name[name] = _latest_timestamp(by_name.get(name), row, config.GOOGLE_FORM_TIMESTAMP_COLUMN)
    return {"by_email": by_email, "by_name": by_name}


def _extract_spreadsheet_id(value):
    if not value:
        return ""
    match = SPREADSHEET_ID_PATTERN.search(value)
    if match:
        return match.group(1)
    return value.strip()


def _spreadsheet_csv_url(spreadsheet_id, sheet_name):
    if sheet_name:
        return (
            f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
            f"?tqx=out:csv&sheet={sheet_name.replace(' ', '%20')}"
        )
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"


def _load_rows_from_url(url):
    with urlopen(url, timeout=20) as resp:
        raw = resp.read().decode("utf-8-sig", errors="ignore")
    return list(csv.DictReader(io.StringIO(raw)))


def _load_rows_from_file(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _load_single_form(form_key, config):
    spreadsheet_urls = getattr(config, "GOOGLE_FORM_SPREADSHEET_URLS", {})
    spreadsheet_value = spreadsheet_urls.get(form_key, "") or getattr(config, "GOOGLE_FORMS_SPREADSHEET_ID", "")
    sheet_name = getattr(config, "GOOGLE_FORM_SHEETS", {}).get(form_key, "")

    spreadsheet_id = _extract_spreadsheet_id(spreadsheet_value)
    if spreadsheet_id:
        url = _spreadsheet_csv_url(spreadsheet_id, sheet_name)
        try:
            rows = _load_rows_from_url(url)
            idx = _build_index(rows, config)
            return {"exists": True, "source": "google_sheets", "error": "", **idx}
        except URLError as err:
            fallback_path = Path(config.GOOGLE_FORM_FILES.get(form_key, ""))
            if fallback_path.exists():
                rows = _load_rows_from_file(fallback_path)
                idx = _build_index(rows, config)
                return {"exists": True, "source": "local_csv_fallback", "error": str(err), **idx}
            return {"exists": False, "source": "google_sheets", "error": str(err), "by_email": {}, "by_name": {}}

    path = Path(config.GOOGLE_FORM_FILES.get(form_key, ""))
    if not path.exists():
        return {"exists": False, "source": "local_csv", "error": "", "by_email": {}, "by_name": {}}

    rows = _load_rows_from_file(path)
    idx = _build_index(rows, config)
    return {"exists": True, "source": "local_csv", "error": "", **idx}


def load_google_form_indexes(config):
    forms = {}
    for form_key in config.GOOGLE_FORM_FILES:
        forms[form_key] = _load_single_form(form_key, config)
    enabled = any(v["exists"] for v in forms.values())
    return {"enabled": enabled, "forms": forms}


def _find_for_form(single_form_index, props, student_name, config):
    if not single_form_index.get("exists"):
        return None

    for email in _emails_for_props(props, config):
        if email in single_form_index["by_email"]:
            return single_form_index["by_email"][email]

    name_key = _norm(student_name)
    if name_key and name_key in single_form_index["by_name"]:
        return single_form_index["by_name"][name_key]

    return None


def get_student_form_summary(indexes, props, student_name, config):
    matches = {}
    total_score = 0
    max_score = sum(config.RUBRIC_WEIGHTS.values())

    for form_key, single_form_index in indexes["forms"].items():
        submission = _find_for_form(single_form_index, props, student_name, config)
        submitted = submission is not None
        if submitted:
            total_score += config.RUBRIC_WEIGHTS.get(form_key, 0)

        matches[form_key] = {
            "submitted": submitted,
            "timestamp": submission.get(config.GOOGLE_FORM_TIMESTAMP_COLUMN, "") if submission else "",
            "submission": submission,
            "source": single_form_index.get("source", ""),
            "error": single_form_index.get("error", ""),
        }

    return {
        "matches": matches,
        "all_forms_submitted": all(m["submitted"] for m in matches.values()) if matches else False,
        "rubric_score": total_score,
        "rubric_max": max_score,
        "rubric_percent": (total_score / max_score) if max_score else 0,
    }
