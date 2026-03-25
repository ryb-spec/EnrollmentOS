# -*- coding: utf-8 -*-
"""
SIMPLIFIED ENROLLMENT DASHBOARD - ACTION FOCUSED

This dashboard answers TWO critical questions:
1. Who needs follow-up TODAY?
2. Who is STUCK or OVERDUE?

Everything else is secondary or removed.
"""

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote_plus, unquote_plus

import config
import extractors
import notion_io
import google_forms
import assess_io
import rubric_components
import email_reminders

ENROLLMENT_GOAL = 102
FILES_PROPERTY_NAME = "Files & media"

# Pipeline stage mapping - STRICT AND EXACT
PIPELINE_STAGE_MAPPING = {
    # Lead
    "New Lead": "Lead",
    "Contacted": "Lead",
    
    # Stage 1 - Intake
    "Intake Sent": "Stage 1 - Intake",
    "Gathering References": "Stage 1 - Intake",
    
    # Stage 2 - Principal Review (14 day max)
    "Under Principal Review": "Stage 2 - Principal Review",
    
    # Stage 3 - Application
    "Application Sent": "Stage 3 - Application",
    "Application Started": "Stage 3 - Application",
    
    # Stage 4 - Interview
    "Application Completed": "Stage 4 - Interview",
    "Scheduling Interview": "Stage 4 - Interview",
    
    # Stage 5 - Decision
    "Accepted": "Stage 5 - Decision",
    "Enrolled": "Stage 5 - Decision",
    
    # Exclude
    "Not a Good Fit": "EXCLUDE",
}

FOLLOW_UP_DAYS_THRESHOLD = 2
STUCK_DAYS_THRESHOLD = 7

STAGE_OVERDUE_RULES = {
    "Stage 2 - Principal Review": 14,  # days
    "Stage 3 - Application": 10,
    "Stage 4 - Interview": 7,
}


def apply_global_styles():
    """Apply clean, simple styling optimized for action-driven workflow."""
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #F9FAFB;
            color: #1F2937;
        }
        .main .block-container {
            max-width: 1200px;
            margin: 0 auto;
            padding-top: 10px;
        }
        h1, h2, h3 {
            color: #111827;
            font-weight: 700;
        }
        .action-card {
            background: #FFFFFF;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,.1);
            padding: 16px;
            margin-bottom: 12px;
        }
        .kpi-card {
            background: #FFFFFF;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,.1);
            padding: 16px;
            text-align: center;
            border-top: 4px solid #3B82F6;
        }
        .kpi-number {
            font-size: 2em;
            font-weight: 700;
            color: #111827;
        }
        .kpi-label {
            font-size: 0.9em;
            color: #6B7280;
            margin-top: 4px;
        }
        /* Color indicators */
        .status-red { background-color: #FEE2E2; border-left: 4px solid #DC2626; }
        .status-yellow { background-color: #FEF3C7; border-left: 4px solid #F59E0B; }
        .status-green { background-color: #DCFCE7; border-left: 4px solid #16A34A; }
        
        [data-testid="stDataFrame"] thead tr th {
            background-color: #374151 !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
        }
        [data-testid="stDataFrame"] tbody tr:nth-child(even) {
            background-color: #F9FAFB !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# Compatibility wrappers for Streamlit
def _rerun():
    if hasattr(st, "rerun"):
        return st.rerun()
    if hasattr(st, "experimental_rerun"):
        return st.experimental_rerun()
    raise RuntimeError("Streamlit rerun not available")


def _toast(message: str, icon: str = "✅"):
    if hasattr(st, "toast"):
        st.toast(message, icon=icon)


def load_pages():
    notion = notion_io.get_notion_client()
    return notion_io.fetch_all_pages_from_databases(notion, config.DATABASES)


@st.cache_data(ttl=300)
def get_normalized_dataset():
    pages = load_pages()
    form_indexes = google_forms.load_google_form_indexes(config)
    df = pages_to_df(pages, form_indexes)
    return df, form_indexes, len(pages)


def extract_files_links(props, prop_name):
    """Extract file links from Notion properties."""
    p = props.get(prop_name)
    if not p or p.get("type") != "files":
        return []
    files = p.get("files") or []
    links = []
    for f in files:
        name = f.get("name") or "Document"
        if f.get("type") == "file":
            url = f.get("file", {}).get("url")
        else:
            url = f.get("external", {}).get("url")
        if url:
            links.append({"name": name, "url": url})
    return links


def map_status_to_stage(status_text: str) -> str:
    """Map Notion Status to pipeline stage. Returns 'EXCLUDE' if not in pipeline."""
    if not status_text:
        return "UNKNOWN"
    
    status_text = status_text.strip()
    
    # Direct mapping
    if status_text in PIPELINE_STAGE_MAPPING:
        return PIPELINE_STAGE_MAPPING[status_text]
    
    # Case-insensitive fallback for common variations
    status_lower = status_text.lower()
    for key, stage in PIPELINE_STAGE_MAPPING.items():
        if key.lower() == status_lower:
            return stage
    
    return "UNKNOWN"


def is_follow_up_needed_today(row) -> bool:
    """
    Check if student needs follow-up TODAY:
    - Next Step is NOT empty
    - AND Last Updated/Contacted >= 2 days ago
    """
    next_step = str(row.get("Next Step", "")).strip()
    if not next_step:
        return False
    
    # Check last activity
    last_contacted = row.get("Last Contacted")
    last_edited = row.get("Last Edited")
    
    def _get_days_ago(dt_val):
        if pd.isna(dt_val):
            return None
        dt = pd.to_datetime(dt_val, errors="coerce")
        if pd.isna(dt):
            return None
        days = (pd.Timestamp.now() - dt).days
        return days
    
    days_since_contact = _get_days_ago(last_contacted)
    days_since_edit = _get_days_ago(last_edited)
    
    max_days = None
    if days_since_contact is not None:
        max_days = days_since_contact
    if days_since_edit is not None:
        if max_days is None:
            max_days = days_since_edit
        else:
            max_days = min(max_days, days_since_edit)
    
    return (max_days is not None) and (max_days >= FOLLOW_UP_DAYS_THRESHOLD)


def is_stuck_or_overdue(row) -> tuple:
    """
    Check if student is STUCK or OVERDUE.
    Returns: (is_stuck_or_overdue: bool, flag: str, days_in_stage: int)
    """
    stage = str(row.get("Pipeline Stage", "")).strip()
    last_activity = row.get("Last Edited") or row.get("Last Contacted")
    
    if pd.isna(last_activity):
        return (False, "", None)
    
    days_since_activity = (pd.Timestamp.now() - pd.to_datetime(last_activity, errors="coerce")).days
    
    # Check general stuck rule: no movement in 7+ days
    if days_since_activity >= STUCK_DAYS_THRESHOLD:
        # Check if stage-specific overdue rule is triggered
        if stage in STAGE_OVERDUE_RULES:
            max_days = STAGE_OVERDUE_RULES[stage]
            if days_since_activity > max_days:
                return (True, "Overdue", days_since_activity)
        
        return (True, "Stuck", days_since_activity)
    
    return (False, "", days_since_activity)


def compute_next_step(row) -> str:
    """Compute the Next Step action based on pipeline stage."""
    stage = str(row.get("Pipeline Stage", "")).strip()
    
    next_step_map = {
        "Lead": "Send Intake Form",
        "Stage 1 - Intake": "Request References",
        "Stage 2 - Principal Review": "Send Application",
        "Stage 3 - Application": "Follow Up on Application",
        "Stage 4 - Interview": "Schedule Interview",
        "Stage 5 - Decision": "Complete Enrollment",
    }
    
    return next_step_map.get(stage, "Review Profile")


def pages_to_df(pages, form_indexes):
    rows = []
    for page in pages:
        props = page.get("properties", {})
        name = extractors.get_title(props)

        def _first_select_like(*prop_names):
            for prop_name in prop_names:
                val = extractors.get_select_like_value(props, prop_name)
                if val:
                    return val
            return ""

        def _first_text_like(*prop_names):
            for prop_name in prop_names:
                val = extractors.get_rich_text(props, prop_name)
                if val:
                    return val
            return ""

        def _first_email_like(*prop_names):
            for prop_name in prop_names:
                p = props.get(prop_name)
                if not p:
                    continue
                if p.get("type") == "email":
                    email_val = (p.get("email") or "").strip()
                    if email_val:
                        return email_val
                text_val = extractors.get_rich_text(props, prop_name)
                if text_val:
                    return text_val
            return ""

        def _first_phone_like(*prop_names):
            for prop_name in prop_names:
                p = props.get(prop_name)
                if not p:
                    continue
                if p.get("type") == "phone_number":
                    phone_val = (p.get("phone_number") or "").strip()
                    if phone_val:
                        return phone_val
                text_val = extractors.get_rich_text(props, prop_name)
                if text_val:
                    return text_val
            return ""

        def _first_checkbox_like(*prop_names):
            for prop_name in prop_names:
                p = props.get(prop_name)
                if not p:
                    continue
                if p.get("type") == "checkbox":
                    return bool(p.get("checkbox"))
                select_val = extractors.get_select_like_value(props, prop_name)
                if select_val:
                    lowered = select_val.strip().lower()
                    if lowered in {"yes", "true", "completed", "accepted", "enrolled"}:
                        return True
                    if lowered in {"no", "false", "not accepted", "declined"}:
                        return False
            return False

        def _first_date_like(*prop_names):
            for prop_name in prop_names:
                p = props.get(prop_name)
                if not p or p.get("type") != "date":
                    continue
                date_obj = p.get("date") or {}
                date_str = date_obj.get("start")
                if date_str:
                    return pd.to_datetime(date_str, errors="coerce")
            return pd.NaT

        source = _first_select_like("Source") or _first_text_like("Source") or page.get("_source", "(unknown)")
        status = _first_select_like("Status")

        if source == config.REENROLLMENT_SOURCE_LABEL:
            assigned = ""
        else:
            owners = extractors.get_multiselect_names(props, config.PROP_ASSIGNED)
            assigned = extractors.owners_str(owners)

        last_edited = page.get("last_edited_time", "")
        days_since_edit = extractors.days_since(last_edited) if last_edited else None

        is_stale = (
            days_since_edit is not None
            and days_since_edit >= config.STALE_DAYS
            and status not in config.EXCLUDE_STALE_STAGES
        )

        form_summary = google_forms.get_student_form_summary(form_indexes, props, name, config)
        staff_rubric_score = extractors.get_number(props, config.PROP_STAFF_RUBRIC_SCORE)
        staff_rubric_status = extractors.get_select_like_value(props, config.PROP_STAFF_RUBRIC_STATUS) or ""

        parent_submission = form_summary["matches"].get("parent", {"submitted": False, "timestamp": ""})
        reference_1_submission = form_summary["matches"].get("reference_1", {"submitted": False, "timestamp": ""})
        reference_2_submission = form_summary["matches"].get("reference_2", {"submitted": False, "timestamp": ""})

        status_lower = status.lower() if status else ""
        all_required_forms_submitted = (
            bool(parent_submission.get("submitted"))
            and bool(reference_1_submission.get("submitted"))
            and bool(reference_2_submission.get("submitted"))
        )
        assessment_status = extractors.get_select_like_value(props, config.PROP_ASSESSMENT_STATUS) or ""
        assessment_status_lower = assessment_status.lower() if assessment_status else ""
        needs_assessment = (
            source == "New Prospects"
            and assessment_status_lower != "completed"
            and not all_required_forms_submitted
        )

        # Determine if auto-prompt should trigger
        should_prompt_assessment = needs_assessment

        principal_review_date = _first_date_like("Principal Review Date")
        today = pd.Timestamp.now().normalize()
        if pd.notna(principal_review_date):
            days_in_review = int((today - principal_review_date.normalize()).days)
        else:
            days_in_review = None

        accepted = _first_checkbox_like("Accepted")
        submitted_application = _first_checkbox_like("Submitted Application")

        review_overdue = bool(days_in_review is not None and days_in_review > 14)
        last_contacted = _first_date_like("Last Contacted")
        days_since_contact = int((today - last_contacted.normalize()).days) if pd.notna(last_contacted) else None
        follow_up_needed = bool(
            (
                (days_since_contact is not None and days_since_contact > 5)
                or (days_since_contact is None and days_since_edit is not None and days_since_edit > 5)
            )
            and not accepted
        )

        created_time = page.get("created_time", "")
        created = pd.to_datetime(created_time) if created_time else pd.NaT

        gender = _first_select_like("Gender")
        grade = _first_select_like("Entering Grade")

        assessment_date = _first_date_like("Assessment Date")
        assessment_document = _first_text_like("Assessment Document")
        if not assessment_document:
            p = props.get("Assessment Document")
            if p and p.get("type") == "url":
                assessment_document = p.get("url") or ""

        current_school = _first_text_like("Current School")
        city = _first_text_like("City")
        state = _first_text_like("State")
        parent_contact = _first_text_like("Parent Contact")
        parent_1_name = _first_text_like("Parent 1 Name")
        parent_1_email = _first_email_like("Parent 1 Email")
        parent_1_phone = _first_phone_like("Parent 1 Phone")
        call_times = _first_text_like("Good times to call")
        track = _first_select_like("Track")
        target_school_year = _first_select_like("Target School Year")
        admissions_process = _first_select_like("Admissions Process")
        notes = _first_text_like("Notes")

        row = {
            "Student Name": name,
            "Name": name,
            "Status": status,
            "Assigned Staff": assigned,
            "Source": source,
            "Track": track,
            "Target School Year": target_school_year,
            "Admissions Process": admissions_process,
            "Assessment Status": assessment_status,
            "Assessment Date": assessment_date,
            "Assessment Document": assessment_document,
            "Submitted Application": submitted_application,
            "Accepted": accepted,
            "Last Contacted": last_contacted,
            "Days Since Contact": days_since_contact,
            "Next Step": "",
            "Days Since Edit": days_since_edit,
            "Last Edited": pd.to_datetime(last_edited) if last_edited else pd.NaT,
            "Created": created,
            "Gender": gender,
            "Entering Grade": grade,
            "Grade": grade,
            "Current School": current_school,
            "City": city,
            "State": state,
            "Parent Contact": parent_contact,
            "Parent 1 Name": parent_1_name,
            "Parent 1 Email": parent_1_email,
            "Parent 1 Phone": parent_1_phone,
            "Good times to call": call_times,
            "Notes": notes,
            "Notion URL": page.get("url", ""),
            "Parent Form Submitted": parent_submission.get("submitted", False),
            "Parent Form Timestamp": parent_submission.get("timestamp", ""),
            "Reference 1 Submitted": reference_1_submission.get("submitted", False),
            "Reference 1 Timestamp": reference_1_submission.get("timestamp", ""),
            "Reference 2 Submitted": reference_2_submission.get("submitted", False),
            "Reference 2 Timestamp": reference_2_submission.get("timestamp", ""),
            "All Forms Submitted": form_summary["all_forms_submitted"],
            "Packet Score": form_summary["rubric_score"],
            "Packet Max": form_summary["rubric_max"],
            "Packet %": form_summary["rubric_percent"],
            "BHH Rubric Score": staff_rubric_score,
            "BHH Rubric Status": staff_rubric_status,
            "Needs BHH Rubric": form_summary["all_forms_submitted"] and staff_rubric_score is None,
            "Needs Assessment": needs_assessment,
            "Should Prompt Assessment": should_prompt_assessment,
            "Principal Review Date": principal_review_date,
            "Days In Review": days_in_review,
            "Review Overdue": review_overdue,
            "Follow Up Needed": follow_up_needed,
            "_files": extract_files_links(props, FILES_PROPERTY_NAME),
            "_is_stale": is_stale,
            "_page_id": page.get("id", ""),
        }
        row["Pipeline Stage"] = compute_pipeline_stage(row)
        row["Next Step"] = compute_next_step(row["Pipeline Stage"])
        rows.append(row)

    # Build DataFrame from collected rows. Always return a DataFrame (empty if no rows).
    df = pd.DataFrame(rows)
    # Normalize expected columns when empty so downstream code can safely reference them
    if df.empty:
        expected_cols = [
            "Student Name",
            "Name",
            "Pipeline Stage",
            "Status",
            "Source",
            "Track",
            "Assigned Staff",
            "Target School Year",
            "Admissions Process",
            "Assessment Status",
            "Assessment Date",
            "Assessment Document",
            "Submitted Application",
            "Accepted",
            "Last Contacted",
            "Days Since Contact",
            "Next Step",
            "Days Since Edit",
            "Last Edited",
            "Created",
            "Gender",
            "Entering Grade",
            "Grade",
            "Current School",
            "City",
            "State",
            "Parent Contact",
            "Parent 1 Name",
            "Parent 1 Email",
            "Parent 1 Phone",
            "Good times to call",
            "Notes",
            "Notion URL",
            "Parent Form Submitted",
            "Parent Form Timestamp",
            "Reference 1 Submitted",
            "Reference 1 Timestamp",
            "Reference 2 Submitted",
            "Reference 2 Timestamp",
            "All Forms Submitted",
            "Packet Score",
            "Packet Max",
            "Packet %",
            "BHH Rubric Score",
            "BHH Rubric Status",
            "Needs BHH Rubric",
            "Needs Assessment",
            "Should Prompt Assessment",
            "Principal Review Date",
            "Days In Review",
            "Review Overdue",
            "Follow Up Needed",
            "_files",
            "_is_stale",
            "_page_id",
        ]
        df = pd.DataFrame(columns=expected_cols)

    return df


def render_pending_item_chip(row, item_key):
    """
    Render a single pending assessment item as a compact clickable chip.
    Returns True if clicked (to trigger assessment).
    """
    name = row["Name"]
    status = row["Status"]
    assigned = row.get("Assigned Staff", "")
    last_edited = row.get("Last Edited", pd.NaT)
    
    # Format fields
    last_updated_str = last_edited.strftime("%m/%d") if pd.notna(last_edited) else ""
    assigned_str = assigned if assigned and assigned != "(unassigned)" else ""
    
    # Build compact display line
    fields = [f"<strong>{name}</strong>", status]
    if assigned_str:
        fields.append(assigned_str)
    if last_updated_str:
        fields.append(last_updated_str)
    
    display_line = " · ".join(fields)
    
    # Render chip with button
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(
            f'<div style="padding:6px 0; font-size:0.85rem;">{display_line}</div>',
            unsafe_allow_html=True,
        )
    with col2:
        return st.button("✏️", key=item_key, help="Complete assessment", width="stretch")


def build_kpi_cards(items):
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        stage_value = item.get("panel_value", item["label"])
        button_key = f"kpi_{str(stage_value).lower().replace(' ', '_').replace('-', '_')}"
        stage_lower = str(stage_value).lower()
        if "stage 1" in stage_lower:
            stage_class = "kpi-stage-1"
        elif "stage 2" in stage_lower:
            stage_class = "kpi-stage-2"
        elif "stage 3" in stage_lower:
            stage_class = "kpi-stage-3"
        elif "stage 4" in stage_lower:
            stage_class = "kpi-stage-4"
        else:
            stage_class = "kpi-stage-default"
        with col:
            st.markdown(
                f"""
                <div class="kpi-card {stage_class}">
                    <div class="kpi-label">{item["label"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(str(item["value"]), key=button_key, width="stretch"):
                st.session_state.selected_row_ids = []
                st.session_state.selected_pipeline_stage = stage_value
                st.session_state.selected_category_type = "pipeline_stage"
                st.session_state.panel_open = True
                st.session_state.panel_category = "Pipeline Stage"
                st.session_state.panel_value = stage_value
                _toast(f"Filter applied: {stage_value}", icon="✅")
                _rerun()


def calculate_admissions_score(row):
    score = 0
    if bool(row.get("All Forms Submitted")):
        score += 3
    bhh_rubric_score = row.get("BHH Rubric Score")
    if pd.notna(bhh_rubric_score):
        score += 2
        if bhh_rubric_score >= 4:
            score += 2
    if row.get("Assigned Staff") != "(unassigned)":
        score += 1
    days_since_edit = row.get("Days Since Edit")
    if days_since_edit is not None and days_since_edit < 7:
        score += 1
    return score


def calculate_last_activity(row):
    def _as_datetime(value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return pd.NaT
        dt_value = pd.to_datetime(value, errors="coerce")
        return dt_value

    candidate_fields = [
        "Last Contacted",
        "Last Updated",
        "Last Edited",
        "Created Date",
        "Created",
        "Parent Form Timestamp",
        "Reference 1 Timestamp",
        "Reference 2 Timestamp",
    ]

    for field_name in candidate_fields:
        dt_value = _as_datetime(row.get(field_name))
        if pd.notna(dt_value):
            return dt_value

    return pd.NaT


def get_suggested_next_action(row):
    pipeline_stage = str(row.get("Pipeline Stage") or "").lower()
    if "stage 1" in pipeline_stage:
        return "Send Assessment"
    if "stage 2" in pipeline_stage:
        return "Send Application"
    if "stage 3" in pipeline_stage:
        return "Follow Up Parent Forms"
    if "stage 4" in pipeline_stage:
        return "Call Family"
    if "stage 5" in pipeline_stage:
        return "Enrollment Complete"
    return "Review Student Profile"


def _format_event_date(value):
    dt_value = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt_value):
        return ""
    return dt_value.strftime("%Y-%m-%d")


def _is_complete_or_closed_status(status_value: str):
    status_lower = str(status_value or "").lower()
    return any(
        term in status_lower
        for term in ["accepted", "enrolled", "prospect - closed", "closed", "confirmed", "committed", "not returning", "withdrawn", "declined", "stage 5"]
    )


def classify_reenrollment_bucket(row, config):
    status_text = str(row.get("Status") or "")
    status_lower = status_text.lower()

    if any(term in status_lower for term in ["not returning", "withdrawn", "declined", "will not return", "not return"]):
        return "Not Returning"

    risk_statuses = {str(x).lower() for x in getattr(config, "RETENTION_RISK_STATUSES", set())}
    if status_lower in risk_statuses or any(risk in status_lower for risk in risk_statuses if risk):
        return "At Risk"

    if any(term in status_lower for term in ["confirmed", "committed", "enrolled"]):
        return "Committed/Confirmed"

    return "In Progress"


def activate_click_filter(filtered_df, category, value):
    row_ids = []
    if "_page_id" in filtered_df.columns:
        row_ids = [x for x in filtered_df["_page_id"].dropna().tolist() if x]

    st.session_state.selected_row_ids = row_ids
    st.session_state.selected_category_type = category
    st.session_state.panel_open = True
    st.session_state.panel_category = category
    st.session_state.panel_value = value

    if category == "pipeline_stage":
        st.session_state.selected_pipeline_stage = value
    else:
        st.session_state.selected_pipeline_stage = ""

    _toast(f"Filter applied: {value}", icon="✅")

    _rerun()


def open_student_drawer(student_row: dict, source: str = ""):
    if not student_row:
        return
    st.session_state.selected_student = dict(student_row)
    _toast(f"Opened: {student_row.get('Name', 'Student')}", icon="👤")
    _rerun()


def render_student_drawer():
    selected_student = st.session_state.get("selected_student")
    if not selected_student:
        st.caption("Select a student from Radar, Actions, or Search to view details.")
        return
    render_student_detail_and_actions(selected_student, "selected_student")


def render_student_detail_and_actions(row: dict, idx_key: str):
    if not row:
        return

    name = row.get("Name", "(unknown)")
    pipeline_stage = row.get("Pipeline Stage", "")
    assigned_staff = row.get("Assigned Staff", "(unassigned)")

    st.markdown(f"### {name}")
    st.markdown(f"**{pipeline_stage}**")
    st.markdown(f"**Assigned:** {assigned_staff}")

    assessment_completed = (str(row.get("Assessment Status", "")).lower() == "completed") or (not bool(row.get("Needs Assessment", False)))
    application_sent = "stage 3" in str(pipeline_stage).lower() or "stage 4" in str(pipeline_stage).lower()
    parent_form_submitted = bool(row.get("Parent Form Submitted"))
    reference_forms_submitted = bool(row.get("Reference 1 Submitted")) and bool(row.get("Reference 2 Submitted"))

    indicator_cols = st.columns(4)
    indicator_cols[0].markdown(f"**Assessment Completed:** {'✅' if assessment_completed else '⚠'}")
    indicator_cols[1].markdown(f"**Application Sent:** {'✅' if application_sent else '⚠'}")
    indicator_cols[2].markdown(f"**Parent Form Submitted:** {'✅' if parent_form_submitted else '⚠'}")
    indicator_cols[3].markdown(f"**Reference Forms Submitted:** {'✅' if reference_forms_submitted else '⚠'}")

    suggested_action = get_suggested_next_action(row)
    st.info(f"Next Action: {suggested_action}")

    command_cols = st.columns(5)
    with command_cols[0]:
        if st.button("Send Assessment", key=f"cmd_send_assessment_{idx_key}", width="stretch"):
            st.session_state.assessment_modal_open = True
            st.session_state.assessment_prospect = (name, dict(row))
            st.session_state.student_command_last_action = "Send Assessment"
            _toast("Assessment action queued", icon="📝")
            _rerun()
    with command_cols[1]:
        if st.button("Send Application", key=f"cmd_send_application_{idx_key}", width="stretch"):
            st.session_state.student_command_last_action = "Send Application"
            _toast("Application action queued", icon="📨")
    with command_cols[2]:
        if st.button("Remind Parent Form", key=f"cmd_remind_parent_{idx_key}", width="stretch"):
            st.session_state.student_command_last_action = "Remind Parent Form"
            _toast("Parent reminder action queued", icon="📩")
    with command_cols[3]:
        if st.button("Schedule Interview", key=f"cmd_schedule_interview_{idx_key}", width="stretch"):
            st.session_state.student_command_last_action = "Schedule Interview"
            _toast("Interview action queued", icon="📅")
    with command_cols[4]:
        if st.button("Mark Accepted", key=f"cmd_mark_accepted_{idx_key}", width="stretch"):
            st.session_state.student_command_last_action = "Mark Accepted"
            _toast("Marked accepted in session", icon="✅")

    if st.session_state.get("student_command_last_action"):
        st.caption(f"Last Action: {st.session_state.get('student_command_last_action')}")

    st.markdown("**Student Timeline**")
    timeline_items = []

    created_text = _format_event_date(row.get("Created"))
    if created_text:
        timeline_items.append(f"Prospect Created — {created_text}")

    assessment_date_text = _format_event_date(row.get("Assessment Date"))
    if assessment_date_text:
        timeline_items.append(f"Assessment Opened — {assessment_date_text}")

    if application_sent:
        app_sent_text = _format_event_date(row.get("Last Activity")) or _format_event_date(row.get("Last Edited"))
        timeline_items.append(f"Application Sent — {app_sent_text or 'Date not available'}")

    parent_form_text = _format_event_date(row.get("Parent Form Timestamp"))
    if parent_form_text:
        timeline_items.append(f"Parent Form Submitted — {parent_form_text}")

    if timeline_items:
        for timeline_item in timeline_items:
            st.markdown(f"- {timeline_item}")
    else:
        st.caption("No timeline events available yet.")


def build_status_cards(status_counts, total_count):
    palette = [
        "#dbeafe",
        "#fef3c7",
        "#dcfce7",
        "#fce7f3",
        "#e0f2fe",
        "#ede9fe",
        "#ffe4e6",
        "#f0f9ff",
    ]

    items = [("All", total_count)] + status_counts
    cols = st.columns(4)
    for i, (status, count) in enumerate(items):
        col = cols[i % 4]
        color = palette[i % len(palette)]
        with col:
            st.markdown(
                f"""<span class="status-badge" style="background:{color};">{status}</span>""",
                unsafe_allow_html=True,
            )
            if st.button(f"{count}\n{status}", key=f"status_btn_{i}", width="stretch"):
                st.session_state.selected_status = status


def render_assessment_modal(prospect_name: str, prospect_data: dict):
    """
    Render assessment rubric. Use `st.modal` when available, otherwise fall back to an expanded
    `st.expander` so older Streamlit versions still show the UI.
    """
    use_modal = hasattr(st, "modal")
    header_text = f"Assessment for {prospect_name}"

    if use_modal:
        ctx = st.modal(header_text)
    else:
        ctx = st.expander(header_text, expanded=True)

    with ctx:
        # Prominent banner inside modal so it's obvious the assessment is open
        st.markdown(
            """
            <div style="background:#FFF4CD;border-left:6px solid #F59E0B;padding:12px;border-radius:8px;margin-bottom:8px;">
                <strong>Assessment Open</strong> - Complete the rubric on this panel. Use the buttons to submit or cancel.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"**Status:** {prospect_data.get('Status','(unknown)')} | **Assigned to:** {prospect_data.get('Assigned Staff','(unassigned)')}")
        st.divider()

        # Two-column layout: left = rubric (wider), right = documents/links
        left_col, right_col = st.columns([5, 1], gap="large")

        # Prepare initial data if this is a revision
        initial_data = {}

        # Left column: Render all rubric sections
        with left_col:
            applicant_data = rubric_components.render_applicant_snapshot("assessment", initial_data)

            st.divider()
            st.subheader("Core Fit Assessment (1–5 Scale)")
            st.write("Check **one** per category. Add brief evidence notes only where needed.")

            division = applicant_data.get("division", "Neiros Division")

            if division == "Neiros Division":
                rubric_data = rubric_components.render_neiros_rubric("assessment", initial_data)
            elif division in {"Legacy Division", "Boys Division"}:
                heading = "### Boys Division (Using General Track Criteria)" if division == "Boys Division" else "### Legacy Division (Boys & Girls – General Track)"
                rubric_data = rubric_components.render_legacy_rubric("assessment", initial_data, heading=heading)
            else:
                rubric_data = {"scores": {}, "notes": {}, "score_list": []}

            st.divider()
            disqualifiers = rubric_components.render_disqualifiers("assessment", initial_data)

            st.divider()
            avg_score = rubric_components.avg_or_none(rubric_data.get("score_list", []))
            rating_data = rubric_components.render_overall_rating(avg_score, disqualifiers.get("disqualified", False), "assessment", initial_data)

            st.divider()
            actions_data = rubric_components.render_next_actions("assessment", initial_data)

            st.divider()

            # Build and display payload preview
            payload = rubric_components.build_assessment_payload(applicant_data, rubric_data, disqualifiers, rating_data, actions_data)

            st.subheader("Assessment Preview")
            st.json({
                "student": payload["student_name"],
                "division": payload["division"],
                "overall_rating": payload["overall_rating"],
                "average_score": payload["average_score"],
                "next_actions": payload["next_actions"],
            })

        # Right column: Documents & quick links
        with right_col:
            st.subheader("Documents & Forms")
            notion_url = prospect_data.get("Notion URL") or prospect_data.get("NotionURL") or ""
            if notion_url:
                st.markdown(f"- [Open Notion page]({notion_url})")

            # Files attached in Notion - surface intake + references first
            files = prospect_data.get("_files") or []
            if files:
                intake_links = []
                reference_links = []
                other_links = []
                for f in files:
                    name = (f.get("name") or "Document").strip()
                    url = f.get("url") or (f.get("external") or {}).get("url") or (f.get("file") or {}).get("url")
                    lname = name.lower()
                    if "intake" in lname or "packet" in lname or "application" in lname:
                        intake_links.append((name, url))
                    elif "reference" in lname or "ref" in lname:
                        reference_links.append((name, url))
                    else:
                        other_links.append((name, url))

                if intake_links:
                    st.markdown("**Intake / Packet**")
                    for n, u in intake_links:
                        if u:
                            st.markdown(f"- [{n}]({u})")

                if reference_links:
                    st.markdown("**References (attachments)**")
                    for n, u in reference_links:
                        if u:
                            st.markdown(f"- [{n}]({u})")

                if other_links:
                    st.markdown("**Other attachments**")
                    for n, u in other_links:
                        if u:
                            st.markdown(f"- [{n}]({u})")
            else:
                st.markdown("No attachments found on Notion page")

            # Parent / reference form submissions
            st.markdown("**Form submissions**")
            parent_sub = prospect_data.get("Parent Form Submitted")
            if parent_sub:
                ts = prospect_data.get("Parent Form Timestamp") or ""
                st.markdown(f"- Parent: ✅ {ts}")
            else:
                st.markdown("- Parent: ❌ Missing")

            ref1 = prospect_data.get("Reference 1 Submitted")
            if ref1:
                ts = prospect_data.get("Reference 1 Timestamp") or ""
                st.markdown(f"- Reference 1: ✅ {ts}")
            else:
                st.markdown("- Reference 1: ❌ Missing")

            ref2 = prospect_data.get("Reference 2 Submitted")
            if ref2:
                ts = prospect_data.get("Reference 2 Timestamp") or ""
                st.markdown(f"- Reference 2: ✅ {ts}")
            else:
                st.markdown("- Reference 2: ❌ Missing")

        # Submit button
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Submit Assessment", key="submit_assessment", width="stretch"):
                # Save to Notion
                notion_result = assess_io.save_assessment_to_notion(prospect_name, payload, config)

                if notion_result["success"]:
                    st.success(f"✅ Assessment saved for {prospect_name}!")

                    # Export to local storage (folder would be configured in production)
                    export_result = assess_io.export_assessment_to_drive(prospect_name, payload, folder_path=None)
                    st.info(f"Assessment data ready for export: {export_result.get('message')}")

                    # Re-run to refresh the dashboard
                    st.session_state.assessment_modal_open = False
                    st.rerun()
                else:
                    st.error(f"❌ Error saving assessment: {notion_result['message']}")

        with col2:
            if st.button("❌ Cancel", key="cancel_assessment", width="stretch"):
                st.session_state.assessment_modal_open = False
                st.rerun()


def render_assessment_fullscreen(prospect_name: str, prospect_data: dict):
    """
    Render the assessment UI as a full-screen page replacement (no modal).
    This avoids modal flicker on some Streamlit versions - used when
    `st.session_state.assessment_modal_open` is True.
    """
    # Scroll browser to top so the assessment is obvious on open
    try:
        components.html("<script>window.scrollTo({top:0,behavior:'smooth'});</script>", height=0)
    except Exception:
        pass

    # Large banner so it's impossible to miss
    st.markdown(
        f"""
        <div style="position:sticky;top:0;z-index:9999;background:#FFF4CD;border-left:6px solid #F59E0B;padding:14px;border-radius:6px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
                <div style="font-size:1.05rem;font-weight:700;">Assessment Open - Please complete the rubric below</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"# Assessment for {prospect_name}")
    st.markdown(f"**Status:** {prospect_data.get('Status','(unknown)')} | **Assigned to:** {prospect_data.get('Assigned Staff','(unassigned)')}")
    st.divider()

    left_col, right_col = st.columns([5, 1], gap="large")

    # Prepare initial data if this is a revision
    initial_data = {}

    with left_col:
        applicant_data = rubric_components.render_applicant_snapshot("assessment", initial_data)

        st.divider()
        st.subheader("Core Fit Assessment (1–5 Scale)")
        st.write("Check **one** per category. Add brief evidence notes only where needed.")

        division = applicant_data.get("division", "Neiros Division")

        if division == "Neiros Division":
            rubric_data = rubric_components.render_neiros_rubric("assessment", initial_data)
        elif division in {"Legacy Division", "Boys Division"}:
            heading = "### Boys Division (Using General Track Criteria)" if division == "Boys Division" else "### Legacy Division (Boys & Girls – General Track)"
            rubric_data = rubric_components.render_legacy_rubric("assessment", initial_data, heading=heading)
        else:
            rubric_data = {"scores": {}, "notes": {}, "score_list": []}

        st.divider()
        disqualifiers = rubric_components.render_disqualifiers("assessment", initial_data)

        st.divider()
        avg_score = rubric_components.avg_or_none(rubric_data.get("score_list", []))
        rating_data = rubric_components.render_overall_rating(avg_score, disqualifiers.get("disqualified", False), "assessment", initial_data)

        st.divider()
        actions_data = rubric_components.render_next_actions("assessment", initial_data)

        st.divider()
        payload = rubric_components.build_assessment_payload(applicant_data, rubric_data, disqualifiers, rating_data, actions_data)

        st.subheader("Assessment Preview")
        st.json({
            "student": payload["student_name"],
            "division": payload["division"],
            "overall_rating": payload["overall_rating"],
            "average_score": payload["average_score"],
            "next_actions": payload["next_actions"],
        })

    with right_col:
        st.subheader("Documents & Forms")
        notion_url = prospect_data.get("Notion URL") or prospect_data.get("NotionURL") or ""
        if notion_url:
            st.markdown(f"- [Open Notion page]({notion_url})")

        files = prospect_data.get("_files") or []
        if files:
            intake_links = []
            reference_links = []
            other_links = []
            for f in files:
                name = (f.get("name") or "Document").strip()
                url = f.get("url") or (f.get("external") or {}).get("url") or (f.get("file") or {}).get("url")
                lname = name.lower()
                if "intake" in lname or "packet" in lname or "application" in lname:
                    intake_links.append((name, url))
                elif "reference" in lname or "ref" in lname:
                    reference_links.append((name, url))
                else:
                    other_links.append((name, url))

            if intake_links:
                st.markdown("**Intake / Packet**")
                for n, u in intake_links:
                    if u:
                        st.markdown(f"- [{n}]({u})")

            if reference_links:
                st.markdown("**References (attachments)**")
                for n, u in reference_links:
                    if u:
                        st.markdown(f"- [{n}]({u})")

            if other_links:
                st.markdown("**Other attachments**")
                for n, u in other_links:
                    if u:
                        st.markdown(f"- [{n}]({u})")
        else:
            st.markdown("No attachments found on Notion page")

        st.markdown("**Form submissions**")
        parent_sub = prospect_data.get("Parent Form Submitted")
        if parent_sub:
            ts = prospect_data.get("Parent Form Timestamp") or ""
            st.markdown(f"- Parent: ✅ {ts}")
        else:
            st.markdown("- Parent: ❌ Missing")

        ref1 = prospect_data.get("Reference 1 Submitted")
        if ref1:
            ts = prospect_data.get("Reference 1 Timestamp") or ""
            st.markdown(f"- Reference 1: ✅ {ts}")
        else:
            st.markdown("- Reference 1: ❌ Missing")

        ref2 = prospect_data.get("Reference 2 Submitted")
        if ref2:
            ts = prospect_data.get("Reference 2 Timestamp") or ""
            st.markdown(f"- Reference 2: ✅ {ts}")
        else:
            st.markdown("- Reference 2: ❌ Missing")

    # Submit / Cancel
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("✅ Submit Assessment", key="submit_assessment_full", width="stretch"):
            notion_result = assess_io.save_assessment_to_notion(prospect_name, payload, config)
            if notion_result.get("success"):
                st.success(f"✅ Assessment saved for {prospect_name}!")
                assess_io.export_assessment_to_drive(prospect_name, payload, folder_path=None)
                st.session_state.assessment_modal_open = False
                st.rerun()
            else:
                st.error(f"❌ Error saving assessment: {notion_result.get('message')}")

    with col2:
        if st.button("❌ Cancel", key="cancel_assessment_full", width="stretch"):
            st.session_state.assessment_modal_open = False
            st.rerun()





def main():
    st.set_page_config(page_title="BHH Enrollment Dashboard", layout="wide")
    if "simple_theme" not in st.session_state:
        st.session_state.simple_theme = True
    with st.sidebar:
        st.checkbox("Simple Theme (recommended)", key="simple_theme")
    apply_global_styles(st.session_state.simple_theme)

    if "forecast_scope" not in st.session_state:
        st.session_state.forecast_scope = "Both"
    if "last_refresh_at" not in st.session_state:
        st.session_state.last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header_col1, header_col2 = st.columns([3, 2])
    with header_col1:
        logo_path = Path("assets/BHH_HORIZ_Logo320x132.png")
        if logo_path.exists():
            st.image(str(logo_path), width=160)
        st.markdown('<h2 class="bhh-title" style="margin-bottom:0;">Enrollment Command Center</h2>', unsafe_allow_html=True)
        st.markdown('<p class="bhh-muted" style="margin-top:2px;">Bader Hillel High School Admissions Dashboard</p>', unsafe_allow_html=True)
    with header_col2:
        st.selectbox(
            "Scope",
            options=["New Prospects", "Reenrollment", "Both"],
            key="forecast_scope",
            label_visibility="visible",
        )
        st.caption(f"Last refreshed: {st.session_state.last_refresh_at}")
        if st.button("🔄 Refresh Data", key="top_refresh_data", width="stretch"):
            _toast("Refreshing data…", icon="🔄")
            get_normalized_dataset.clear()
            st.session_state.last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _rerun()

    active_chips = []
    if st.session_state.get("selected_pipeline_stage"):
        active_chips.append(f"Pipeline: {st.session_state['selected_pipeline_stage']}")
    if st.session_state.get("quick_filter"):
        active_chips.append(f"Quick Filter: {st.session_state['quick_filter']}")
    if st.session_state.get("selected_source") and st.session_state.get("selected_source") != "All":
        active_chips.append(f"View: {st.session_state['selected_source']}")
    if active_chips:
        chips_html = "".join([f'<span class="filter-pill">{chip}</span>' for chip in active_chips])
        st.markdown(chips_html, unsafe_allow_html=True)
    st.divider()
    
    # Test reminder button in sidebar (only when email reminders enabled)
    with st.sidebar:
        st.markdown("---")
        st.subheader("⚙️ Admin Tools")
        if st.button("🔄 Refresh Data Now", width="stretch"):
            _toast("Refreshing data…", icon="🔄")
            get_normalized_dataset.clear()
            st.session_state.last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _rerun()
        if getattr(config, "EMAIL_ENABLED", False):
            if st.button("📧 Send Test Reminders Now", width="stretch"):
                with st.spinner("Sending reminders..."):
                    result = email_reminders.send_reminder_batch()
                    st.info(f"✅ **Sent:** {result.get('sent', 0)} | **Skipped:** {result.get('skipped', 0)} | **Pending:** {result.get('pending_total', 0)}")
                    if result.get("errors"):
                        st.error(f"⚠️  Errors: {', '.join(result['errors'])}")
        else:
            st.info("Email reminders currently disabled")
        # Debug helper: optionally show session state for troubleshooting
        if st.checkbox("Show debug state", key="show_debug_state"):
            st.write({k: (v if k in ["assessment_modal_open", "assessment_prospect"] else "(hidden)") for k, v in st.session_state.items()})

    df, form_indexes, pages_count = get_normalized_dataset()

    form_errors = [f"{k}: {v.get('error')}" for k, v in form_indexes["forms"].items() if v.get("error")]
    if form_errors:
        st.warning("Google Forms source warning: " + " | ".join(form_errors))

    with st.sidebar:
        with st.expander("Data Health", expanded=False):
            prospects_count = int((df["Source"] == "New Prospects").sum()) if "Source" in df.columns else 0
            missing_email = int((df.get("Parent 1 Email", pd.Series(dtype=str)).fillna("").astype(str).str.strip() == "").sum())
            missing_assessment_status = int((df.get("Assessment Status", pd.Series(dtype=str)).fillna("").astype(str).str.strip() == "").sum())
            missing_assigned_staff = int((df.get("Assigned Staff", pd.Series(dtype=str)).fillna("(unassigned)") == "(unassigned)").sum())
            st.write({
                "pages_count": pages_count,
                "prospects": prospects_count,
                "missing_email": missing_email,
                "missing_assessment_status": missing_assessment_status,
                "missing_assigned_staff": missing_assigned_staff,
            })

    # Support opening an assessment directly via query params (new tab)
    params = _get_query_params()
    if params.get("assessment") and params.get("name"):
        try:
            target_name = unquote_plus(params.get("name")[0])
            match = df[df["Name"] == target_name]
            if not match.empty:
                prospect_row = match.iloc[0]
                prospect_name = prospect_row["Name"]
                prospect_data = prospect_row.to_dict()
                # Render assessment immediately (modal if available, else fullscreen)
                if hasattr(st, "modal"):
                    render_assessment_modal(prospect_name, prospect_data)
                else:
                    render_assessment_fullscreen(prospect_name, prospect_data)
                # Provide a small return link that clears the query params
                if st.button("Return to dashboard"):
                    _set_query_params()
                    _rerun()
                return
        except Exception:
            pass

    if "selected_stage" not in st.session_state:
        st.session_state.selected_stage = "All"
    if "selected_status" not in st.session_state:
        st.session_state.selected_status = "All"
    if "selected_source" not in st.session_state:
        st.session_state.selected_source = "All"
    if "assessment_modal_open" not in st.session_state:
        st.session_state.assessment_modal_open = False
    if "assessment_prospect" not in st.session_state:
        st.session_state.assessment_prospect = None
    if "panel_open" not in st.session_state:
        st.session_state.panel_open = False
    if "panel_category" not in st.session_state:
        st.session_state.panel_category = ""
    if "panel_value" not in st.session_state:
        st.session_state.panel_value = ""
    if "selected_pipeline_stage" not in st.session_state:
        st.session_state.selected_pipeline_stage = ""
    if "selected_category_type" not in st.session_state:
        st.session_state.selected_category_type = ""
    if "selected_row_ids" not in st.session_state:
        st.session_state.selected_row_ids = []
    if "selected_student" not in st.session_state:
        st.session_state.selected_student = None
    if "quick_filter" not in st.session_state:
        st.session_state.quick_filter = ""
    if "follow_up_contacted_ids" not in st.session_state:
        st.session_state.follow_up_contacted_ids = set()
    if "follow_up_last_action" not in st.session_state:
        st.session_state.follow_up_last_action = ""

    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    df = df.copy()
    df["Pipeline Stage"] = df.apply(compute_pipeline_stage, axis=1)
    df["Next Step"] = df["Pipeline Stage"].apply(compute_next_step)
    df["Last Activity"] = df.apply(calculate_last_activity, axis=1)
    last_activity_series = pd.to_datetime(df["Last Activity"], errors="coerce", utc=True).dt.tz_localize(None)
    df["Days Since Activity"] = (today - last_activity_series).dt.days
    df["Days Since Activity"] = df["Days Since Activity"].fillna(9999).astype(int)
    last_contacted_series = pd.to_datetime(df["Last Contacted"], errors="coerce", utc=True).dt.tz_localize(None)
    df["Days Since Contact"] = (today - last_contacted_series).dt.days
    days_since_contact_numeric = pd.to_numeric(df["Days Since Contact"], errors="coerce")
    missing_last_contacted_mask = last_contacted_series.isna()

    follow_up_mask = days_since_contact_numeric > 5
    follow_up_mask = follow_up_mask | (missing_last_contacted_mask & (df["Days Since Activity"] > 5))
    follow_up_mask = follow_up_mask & (~df["Accepted"].fillna(False))
    contacted_ids = st.session_state.get("follow_up_contacted_ids") or set()
    if contacted_ids and "_page_id" in df.columns:
        follow_up_mask = follow_up_mask & (~df["_page_id"].isin(list(contacted_ids)))
    df["Follow Up Needed"] = follow_up_mask.fillna(False)

    source_options = ["All"] + [label for label, _ in config.DATABASES]
    st.markdown("")
    st.selectbox("Select view", source_options, key="selected_source")

    base_df = df.copy()
    if st.session_state.selected_source == "All":
        base_df = base_df[base_df["Source"] == "New Prospects"]
    else:
        base_df = base_df[base_df["Source"] == st.session_state.selected_source]
    base_df = base_df.copy()
    base_df["Admissions Score"] = base_df.apply(calculate_admissions_score, axis=1)

    stage_order = [
        "Stage 1 - Active Prospect",
        "Stage 2 - Principal Review",
        "Stage 3 - Application Sent",
        "Stage 4 - Awaiting Decision",
        "Stage 5 - Enrolled",
    ]
    stage_counts = base_df.groupby("Pipeline Stage").size() if not base_df.empty else pd.Series(dtype=int)
    stage_kpi_items = []
    for stage_name in stage_order:
        stage_kpi_items.append(
            {
                "label": stage_name,
                "value": int(stage_counts.get(stage_name, 0)),
                "panel_value": stage_name,
            }
        )

    st.markdown('<div class="bhh-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="bhh-title">Pipeline Stages</h3>', unsafe_allow_html=True)
    build_kpi_cards(stage_kpi_items)
    st.markdown('</div>', unsafe_allow_html=True)

    follow_up_needed_df = base_df[base_df["Follow Up Needed"]].copy()
    followup_kpi_col, followup_meta_col = st.columns([1, 4])
    with followup_kpi_col:
        st.markdown('<div class="kpi-card"><div class="kpi-label">Follow-Up Needed</div></div>', unsafe_allow_html=True)
        if st.button(str(len(follow_up_needed_df)), key="kpi_followup_needed", width="stretch"):
            activate_click_filter(follow_up_needed_df, "health_metric", "Follow-Up Needed")
    with followup_meta_col:
        if st.session_state.get("follow_up_last_action"):
            st.caption(f"Action Center: {st.session_state.get('follow_up_last_action')}")

    st.markdown('<div class="bhh-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="bhh-title">📊 Forecast & Pipeline Health</h3>', unsafe_allow_html=True)
    st.caption("Scope affects Forecast & Pipeline Health only.")

    forecast_source_df = df.copy()
    prospects_df_all = forecast_source_df[forecast_source_df["Source"] == "New Prospects"].copy()
    reenrollment_df_all = forecast_source_df[forecast_source_df["Source"] == config.REENROLLMENT_SOURCE_LABEL].copy()

    include_prospects = st.session_state.forecast_scope in {"New Prospects", "Both"}
    include_reenrollment = st.session_state.forecast_scope in {"Reenrollment", "Both"}

    prospects_scope_df = prospects_df_all.copy() if include_prospects else prospects_df_all.iloc[0:0].copy()
    reenrollment_scope_df = reenrollment_df_all.copy() if include_reenrollment else reenrollment_df_all.iloc[0:0].copy()

    with st.expander("Adjust Forecast Rates", expanded=False):
        st.markdown("**Prospect Pipeline Rates**")
        prospect_rates = {}
        for stage_name, default_rate in FORECAST_RATES_PROSPECTS_DEFAULT.items():
            prospect_rates[stage_name] = st.slider(
                f"{stage_name}",
                min_value=0.0,
                max_value=1.0,
                value=float(default_rate),
                step=0.01,
                key=f"rate_pros_{stage_name}",
            )

        st.markdown("**Reenrollment Retention Rates**")
        reenrollment_rates = {}
        for bucket_name, default_rate in REENROLLMENT_RETENTION_DEFAULT.items():
            reenrollment_rates[bucket_name] = st.slider(
                f"{bucket_name}",
                min_value=0.0,
                max_value=1.0,
                value=float(default_rate),
                step=0.01,
                key=f"rate_reen_{bucket_name}",
            )

    prospects_active_df = prospects_scope_df[prospects_scope_df["Pipeline Stage"] != "Stage 5 - Enrolled"].copy()
    prospect_rows = []
    for stage_name, rate in prospect_rates.items():
        stage_df = prospects_active_df[prospects_active_df["Pipeline Stage"] == stage_name]
        stage_count = len(stage_df)
        prospect_rows.append(
            {
                "Stage": stage_name,
                "Count": stage_count,
                "Rate": rate,
                "Expected": stage_count * rate,
                "_rows": stage_df,
            }
        )
    prospect_forecast_df = pd.DataFrame([{k: v for k, v in item.items() if k != "_rows"} for item in prospect_rows])
    expected_new_enrollments = float(prospect_forecast_df["Expected"].sum()) if not prospect_forecast_df.empty else 0.0

    reenrollment_scope_df = reenrollment_scope_df.copy()
    if not reenrollment_scope_df.empty:
        reenrollment_scope_df["Reenrollment Bucket"] = reenrollment_scope_df.apply(
            lambda row: classify_reenrollment_bucket(row, config), axis=1
        )

    reenrollment_rows = []
    for bucket_name, rate in reenrollment_rates.items():
        if "Reenrollment Bucket" in reenrollment_scope_df.columns:
            bucket_df = reenrollment_scope_df[reenrollment_scope_df["Reenrollment Bucket"] == bucket_name]
        else:
            bucket_df = reenrollment_scope_df.iloc[0:0]
        bucket_count = len(bucket_df)
        reenrollment_rows.append(
            {
                "Bucket": bucket_name,
                "Count": bucket_count,
                "Rate": rate,
                "Expected Retained": bucket_count * rate,
                "_rows": bucket_df,
            }
        )
    reenrollment_forecast_df = pd.DataFrame([{k: v for k, v in item.items() if k != "_rows"} for item in reenrollment_rows])
    expected_retained = float(reenrollment_forecast_df["Expected Retained"].sum()) if not reenrollment_forecast_df.empty else 0.0

    expected_total = (expected_new_enrollments if include_prospects else 0.0) + (expected_retained if include_reenrollment else 0.0)

    prospects_complete_mask = prospects_scope_df["Status"].apply(_is_complete_or_closed_status)
    prospects_contact_days = pd.to_numeric(prospects_scope_df["Days Since Contact"], errors="coerce")
    prospects_stalled_df = prospects_scope_df[(prospects_contact_days >= 10) & (~prospects_complete_mask)]
    prospects_follow_up_df = prospects_scope_df[(prospects_scope_df["Follow Up Needed"]) & (~prospects_complete_mask)]
    prospects_missing_next_df = prospects_scope_df[prospects_scope_df["Next Step"] == ""]
    prospects_missing_staff_df = prospects_scope_df[prospects_scope_df["Assigned Staff"] == "(unassigned)"]
    prospects_principal_overdue_df = prospects_scope_df[
        (prospects_scope_df["Pipeline Stage"] == "Stage 2 - Principal Review")
        & (prospects_scope_df["Days In Review"].fillna(0) > 14)
    ]

    reenrollment_complete_mask = reenrollment_scope_df["Status"].apply(_is_complete_or_closed_status) if not reenrollment_scope_df.empty else pd.Series([], dtype=bool)
    reenrollment_contact_days = pd.to_numeric(reenrollment_scope_df["Days Since Contact"], errors="coerce") if not reenrollment_scope_df.empty else pd.Series([], dtype=float)
    reenrollment_stalled_df = reenrollment_scope_df[(reenrollment_contact_days >= 10) & (~reenrollment_complete_mask)] if not reenrollment_scope_df.empty else reenrollment_scope_df
    reenrollment_follow_up_df = reenrollment_scope_df[(reenrollment_scope_df["Follow Up Needed"]) & (~reenrollment_complete_mask)] if not reenrollment_scope_df.empty else reenrollment_scope_df
    reenrollment_missing_next_df = reenrollment_scope_df[reenrollment_scope_df["Next Step"] == ""] if not reenrollment_scope_df.empty else reenrollment_scope_df
    reenrollment_missing_staff_df = reenrollment_scope_df[reenrollment_scope_df["Assigned Staff"] == "(unassigned)"] if (not reenrollment_scope_df.empty and "Assigned Staff" in reenrollment_scope_df.columns) else reenrollment_scope_df.iloc[0:0]

    stalled_df = pd.concat([prospects_stalled_df, reenrollment_stalled_df], ignore_index=True)
    follow_up_health_df = pd.concat([prospects_follow_up_df, reenrollment_follow_up_df], ignore_index=True)
    missing_next_df = pd.concat([prospects_missing_next_df, reenrollment_missing_next_df], ignore_index=True)
    missing_staff_df = pd.concat([prospects_missing_staff_df, reenrollment_missing_staff_df], ignore_index=True)
    principal_overdue_df = prospects_principal_overdue_df.copy()

    health_score = 100
    health_score -= 2 * len(stalled_df)
    health_score -= 2 * len(follow_up_health_df)
    health_score -= 3 * len(principal_overdue_df)
    health_score -= 1 * len(missing_next_df)
    health_score -= 1 * len(missing_staff_df)
    health_score = max(0, min(100, int(health_score)))

    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        if st.button(f"Expected New Enrollments\n{expected_new_enrollments:.1f}", key="kpi_expected_new", width="stretch"):
            activate_click_filter(prospects_active_df, "forecast_group", "Expected New Enrollments")
    with kpi_cols[1]:
        if st.button(f"Expected Retained\n{expected_retained:.1f}", key="kpi_expected_retained", width="stretch"):
            activate_click_filter(reenrollment_scope_df, "forecast_group", "Expected Retained")
    with kpi_cols[2]:
        goal_gap = expected_total - ENROLLMENT_GOAL
        if st.button(f"Expected Total\n{expected_total:.1f}", key="kpi_expected_total", width="stretch"):
            combined_scope_df = pd.concat([prospects_scope_df, reenrollment_scope_df], ignore_index=True)
            activate_click_filter(combined_scope_df, "forecast_group", "Expected Total")
        st.caption(f"Goal: {ENROLLMENT_GOAL} ({goal_gap:+.1f})")
    with kpi_cols[3]:
        if st.button(f"Pipeline Health Score\n{health_score}", key="kpi_health_score", width="stretch"):
            combined_health_df = pd.concat([stalled_df, follow_up_health_df, missing_next_df, missing_staff_df, principal_overdue_df], ignore_index=True)
            activate_click_filter(combined_health_df.drop_duplicates(subset=["_page_id"]), "health_metric", "Pipeline Health Score")

    forecast_cols = st.columns(2)
    with forecast_cols[0]:
        if include_prospects:
            st.markdown("**Prospect Forecast**")
            prospect_display_df = prospect_forecast_df[["Stage", "Count", "Rate", "Expected"]].copy()
            st.dataframe(prospect_display_df, width="stretch", hide_index=True, height=210)

    with forecast_cols[1]:
        if include_reenrollment:
            st.markdown("**Reenrollment Retention Forecast**")
            reenrollment_display_df = reenrollment_forecast_df.rename(
                columns={"Bucket": "Stage", "Expected Retained": "Expected"}
            )[["Stage", "Count", "Rate", "Expected"]].copy()
            st.dataframe(reenrollment_display_df, width="stretch", hide_index=True, height=210)

    health_cols = st.columns(5)
    with health_cols[0]:
        if st.button(f"Stalled\n{len(stalled_df)}", key="health_stalled", width="stretch"):
            activate_click_filter(stalled_df, "health_metric", "Stalled")
    with health_cols[1]:
        if st.button(f"Follow-Up Needed\n{len(follow_up_health_df)}", key="health_followup", width="stretch"):
            activate_click_filter(follow_up_health_df, "health_metric", "Follow-Up Needed")
    with health_cols[2]:
        if st.button(f"Missing Next Step\n{len(missing_next_df)}", key="health_missing_next", width="stretch"):
            activate_click_filter(missing_next_df, "health_metric", "Missing Next Step")
    with health_cols[3]:
        missing_staff_label = f"Missing Staff\n{len(missing_staff_df)}"
        if st.button(missing_staff_label, key="health_missing_staff", width="stretch"):
            activate_click_filter(missing_staff_df, "health_metric", "Missing Assigned Staff")
    with health_cols[4]:
        if st.button(f"Principal Overdue\n{len(principal_overdue_df)}", key="health_principal_overdue", width="stretch"):
            activate_click_filter(principal_overdue_df, "health_metric", "Principal Review Overdue")
    st.markdown('</div>', unsafe_allow_html=True)

    total_count = len(base_df)
    missing_assigned = ((base_df["Source"] != config.REENROLLMENT_SOURCE_LABEL) & (base_df["Assigned Staff"] == "(unassigned)")).sum()
    missing_next_step = (base_df["Next Step"] == "").sum()
    missing_form_packet = (~base_df["All Forms Submitted"]).sum()
    needs_assessment_count = int(base_df["Needs Assessment"].sum())
    stale_count = base_df["_is_stale"].sum()

    # Check for pending assessments that should auto-prompt
    pending_assessments = base_df[base_df["Should Prompt Assessment"]]
    if len(pending_assessments) > 0 and not st.session_state.assessment_modal_open:
        st.warning(f"⏰ **{len(pending_assessments)} assessments pending!**")
        
        # Compact grid display: top 8 items in 2-column layout (4 per column)
        top_n = 8
        pending_display = pending_assessments.head(top_n)
        
        # Split into 2 columns with 4 items each
        col1, col2 = st.columns(2, gap="small")
        
        for idx, (_, prow) in enumerate(pending_display.iterrows()):
            # Determine which column this item goes into
            target_col = col1 if idx < 4 else col2
            
            with target_col:
                # Render compact chip with click handler
                item_key = f"pending_assess_{prow.get('_page_id', idx)}"
                if render_pending_item_chip(prow, item_key):
                    st.session_state.assessment_modal_open = True
                    st.session_state.assessment_prospect = (prow['Name'], prow.to_dict())
                    st.rerun()
        
        # Show more expander if more than top_n
        if len(pending_assessments) > top_n:
            with st.expander(f"Show {len(pending_assessments) - top_n} more"):
                # Grid layout for additional items (2 columns)
                col1, col2 = st.columns(2, gap="small")
                
                for idx, (_, prow) in enumerate(pending_assessments.iloc[top_n:].iterrows()):
                    # Determine which column this item goes into
                    target_col = col1 if idx % 2 == 0 else col2
                    
                    with target_col:
                        # Render compact chip with click handler
                        item_key = f"pending_assess_more_{prow.get('_page_id', top_n + idx)}"
                        if render_pending_item_chip(prow, item_key):
                            st.session_state.assessment_modal_open = True
                            st.session_state.assessment_prospect = (prow['Name'], prow.to_dict())
                            st.rerun()

    st.markdown('<div class="bhh-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="bhh-title">Admissions Action Center</h3>', unsafe_allow_html=True)
    action_center_df = base_df[base_df["Follow Up Needed"]].copy()
    action_center_df["_Days Since Contact Sort"] = pd.to_numeric(action_center_df["Days Since Contact"], errors="coerce").fillna(-1)
    action_center_df = action_center_df.sort_values("_Days Since Contact Sort", ascending=False)

    if action_center_df.empty:
        st.caption("No prospects currently need follow-up.")
    else:
        action_table = action_center_df[["Name", "Pipeline Stage", "Days Since Contact", "Assigned Staff"]].rename(
            columns={"Name": "Student", "Pipeline Stage": "Stage"}
        )
        st.dataframe(action_table, width="stretch", hide_index=True, height=220)

        st.markdown("**Quick Actions**")
        for _, row in action_center_df.head(15).iterrows():
            row_id = row.get("_page_id", row.get("Name", "row"))
            line_col, btn1_col, btn2_col, btn3_col = st.columns([4, 2, 2, 2])
            with line_col:
                contact_days_label = "n/a" if pd.isna(row.get("Days Since Contact")) else f"{int(row['Days Since Contact'])}d"
                st.markdown(f"{row['Name']} · {row['Pipeline Stage']} · {contact_days_label}")
            with btn1_col:
                if st.button("Send Follow Up Email", key=f"followup_email_{row_id}", width="stretch"):
                    st.session_state.selected_student = row.to_dict()
                    st.session_state.follow_up_last_action = f"Follow-up queued for {row['Name']}"
                    _toast("Follow-up action queued", icon="📧")
            with btn2_col:
                if st.button("Open Student", key=f"followup_open_{row_id}", width="stretch"):
                    open_student_drawer(row.to_dict(), source="action_center")
            with btn3_col:
                if st.button("Mark Contacted", key=f"followup_mark_{row_id}", width="stretch"):
                    if "follow_up_contacted_ids" not in st.session_state:
                        st.session_state.follow_up_contacted_ids = set()
                    st.session_state.follow_up_contacted_ids.add(row_id)
                    st.session_state.follow_up_last_action = f"Marked contacted: {row['Name']}"
                    _toast("Marked contacted", icon="✅")
                    _rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    likely_to_enroll = base_df[base_df["Pipeline Stage"] == "Stage 4 - Awaiting Decision"].head(5)
    base_contact_days = pd.to_numeric(base_df["Days Since Contact"], errors="coerce")
    base_missing_contact = pd.to_datetime(base_df["Last Contacted"], errors="coerce", utc=True).isna()
    going_cold_mask = (base_contact_days > 10) | (base_missing_contact & (base_df["Days Since Activity"] > 10))
    going_cold = base_df[going_cold_mask].sort_values("Days Since Activity", ascending=False).head(5)
    needs_attention = base_df[
        (~base_df["Submitted Application"])
        | (base_df["Assessment Status"].fillna("").astype(str).str.strip() == "")
    ].head(5)

    st.markdown('<div class="bhh-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="bhh-title">📡 Admissions Radar</h3>', unsafe_allow_html=True)
    radar_col1, radar_col2, radar_col3 = st.columns(3)
    with radar_col1:
        st.markdown("**Likely to Enroll**")
        for _, row in likely_to_enroll.iterrows():
            item_key = row.get("_page_id", row.get("Name", "item"))
            if st.button(f"{row['Name']} ({row['Admissions Score']})", key=f"radar_likely_{item_key}", width="stretch"):
                open_student_drawer(row.to_dict(), source="radar_likely")
    with radar_col2:
        st.markdown("**Going Cold**")
        for _, row in going_cold.iterrows():
            item_key = row.get("_page_id", row.get("Name", "item"))
            cold_days_label = "n/a" if pd.isna(row.get("Days Since Contact")) else f"{int(row['Days Since Contact'])}d"
            if st.button(f"{row['Name']} ({cold_days_label})", key=f"radar_cold_{item_key}", width="stretch"):
                open_student_drawer(row.to_dict(), source="radar_cold")
    with radar_col3:
        st.markdown("**Needs Attention**")
        for _, row in needs_attention.iterrows():
            item_key = row.get("_page_id", row.get("Name", "item"))
            if st.button(row["Name"], key=f"radar_attention_{item_key}", width="stretch"):
                open_student_drawer(row.to_dict(), source="radar_attention")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("")
    
    # =========================================================================
    # DATAFRAME FILTERING PIPELINE
    # =========================================================================
    # This block documents the complete filtering chain that controls which
    # records appear in the student/prospect list and search results.
    #
    # Pipeline:
    #   base_df (all records)
    #     ↓ Views multiselect (OR logic)
    #   views_filtered_df
    #     ↓ Status selector
    #   df_filtered
    #     ↓ Checkbox filters (stale, unassigned, etc.)
    #   df_filtered
    #     ↓ Extract table columns and sort
    #   display_df (shown in list above + used for drill-down)
    #     ↓ Gender/Grade multiselect filters
    #   drill_down_df (used for search/selection)
    #     ↓ Search query (substring match on Name)
    #   Final results displayed for user selection → drill-down action
    # =========================================================================
    
    # Views multiselect filter - applies OR logic to dataframe
    stage_view_options = sorted([v for v in base_df["Pipeline Stage"].unique() if v and isinstance(v, str)])
    status_view_options = sorted([v for v in base_df["Status"].unique() if v and isinstance(v, str)])
    view_options = stage_view_options + status_view_options + [
        "Reenrollment Retention Risk",
        "Missing Assigned Staff",
        "Missing Next Step",
        "Stale >= 14 days",
        "Incomplete Form Packet",
        "Ready for Assessment",
    ]

    grade_col = "Grade"
    selected_genders = []
    selected_grades = []

    with st.expander("Filters", expanded=False):
        selected_views = st.multiselect(
            "Views",
            options=view_options,
            default=[],
            help="Select one or more views to filter the list. Multiple selections use OR logic."
        )

        stage_status_cols = st.columns(2)
        stage_options = ["All"] + stage_view_options
        status_options = ["All"] + status_view_options
        stage_status_cols[0].selectbox("Stage", stage_options, key="selected_stage")
        stage_status_cols[1].selectbox("Status", status_options, key="selected_status")

        filter_cols = st.columns(6)
        stale_only = filter_cols[0].checkbox("Stale only", value=False)
        unassigned_only = filter_cols[1].checkbox("Unassigned only", value=False)
        missing_next_step_only = filter_cols[2].checkbox("Missing Next Step only", value=False)
        incomplete_packet_only = filter_cols[3].checkbox("Incomplete forms only", value=False)
        needs_rubric_only = filter_cols[4].checkbox("Needs BHH rubric", value=False)
        needs_assessment_only = filter_cols[5].checkbox("Needs Assessment", value=False)

        quick_filter_cols = st.columns(5)
        if quick_filter_cols[0].button("Needs Follow-Up", width="stretch"):
            st.session_state.quick_filter = "follow_up"
        if quick_filter_cols[1].button("Missing Forms", width="stretch"):
            st.session_state.quick_filter = "missing_forms"
        if quick_filter_cols[2].button("Principal Review", width="stretch"):
            st.session_state.quick_filter = "principal_review"
        if quick_filter_cols[3].button("Awaiting Decision", width="stretch"):
            st.session_state.quick_filter = "awaiting_decision"
        if quick_filter_cols[4].button("Clear", width="stretch"):
            st.session_state.quick_filter = ""

        if st.button("Clear KPI Filter", key="clear_kpi_filter_simple", width="content"):
            st.session_state.selected_row_ids = []
            st.session_state.selected_pipeline_stage = ""
            st.session_state.selected_category_type = ""
            st.session_state.panel_open = False
            st.session_state.panel_category = ""
            st.session_state.panel_value = ""
            _toast("Filter cleared", icon="🧹")
            _rerun()

        gender_grade_cols = st.columns(2)
        derived_gender_values = sorted([v for v in base_df["Gender"].unique() if v and isinstance(v, str)])
        grade_values = sorted([str(v).strip() for v in base_df[grade_col].dropna().unique() if str(v).strip()])
        selected_genders = gender_grade_cols[0].multiselect("Gender", options=derived_gender_values, default=[])
        selected_grades = gender_grade_cols[1].multiselect("Grade", options=grade_values, default=[])

    # STEP 1: Apply Views filter (OR logic)
    views_filtered_df = apply_views_filter(base_df, selected_views, config)

    # STEP 2: Apply Stage/Status selectors
    df_filtered = views_filtered_df.copy()
    if st.session_state.selected_stage != "All":
        df_filtered = df_filtered[df_filtered["Pipeline Stage"] == st.session_state.selected_stage]
    if st.session_state.selected_status != "All":
        df_filtered = df_filtered[df_filtered["Status"] == st.session_state.selected_status]
    if (
        st.session_state.get("selected_category_type") == "pipeline_stage"
        and st.session_state.get("selected_pipeline_stage")
    ):
        df_filtered = df_filtered[
            df_filtered["Pipeline Stage"] == st.session_state["selected_pipeline_stage"]
        ]
    if st.session_state.get("selected_row_ids"):
        df_filtered = df_filtered[df_filtered["_page_id"].isin(st.session_state["selected_row_ids"])]

    # STEP 3: Apply additional checkbox filters (AND logic)
    if stale_only:
        df_filtered = df_filtered[df_filtered["_is_stale"]]
    if unassigned_only:
        df_filtered = df_filtered[(df_filtered["Source"] != config.REENROLLMENT_SOURCE_LABEL) & (df_filtered["Assigned Staff"] == "(unassigned)")]
    if missing_next_step_only:
        df_filtered = df_filtered[df_filtered["Next Step"] == ""]
    if incomplete_packet_only:
        df_filtered = df_filtered[~df_filtered["All Forms Submitted"]]
    if needs_rubric_only:
        df_filtered = df_filtered[df_filtered["Needs BHH Rubric"]]
    if needs_assessment_only:
        df_filtered = df_filtered[df_filtered["Needs Assessment"]]

    if st.session_state.quick_filter == "follow_up":
        df_filtered = df_filtered[df_filtered["Follow Up Needed"]]
    elif st.session_state.quick_filter == "missing_forms":
        df_filtered = df_filtered[~df_filtered["All Forms Submitted"]]
    elif st.session_state.quick_filter == "principal_review":
        df_filtered = df_filtered[df_filtered["Pipeline Stage"] == "Stage 2 - Principal Review"]
    elif st.session_state.quick_filter == "awaiting_decision":
        df_filtered = df_filtered[df_filtered["Pipeline Stage"] == "Stage 4 - Awaiting Decision"]

    # STEP 4: Create display dataframe (for table and drill-down base)
    # This is the result of Views + Status + Checkbox filters
    table_cols = [
        "Name",
        "Source",
        "Pipeline Stage",
        "Status",
        "Assigned Staff",
        "Next Step",
        "Days Since Contact",
        "Days Since Edit",
        "Days In Review",
        "Review Overdue",
        "Last Edited",
        "All Forms Submitted",
        "Packet Score",
        "Packet Max",
        "Packet %",
        "BHH Rubric Score",
        "BHH Rubric Status",
        "Parent Form Submitted",
        "Parent Form Timestamp",
        "Reference 1 Submitted",
        "Reference 1 Timestamp",
        "Reference 2 Submitted",
        "Reference 2 Timestamp",
        "Notion URL",
        "Actions",
    ]

    df_filtered = df_filtered.copy()
    df_filtered["Actions"] = "Open"

    display_df = df_filtered[table_cols + ["_files", "_page_id", "Gender", "Grade"]].sort_values(
        by=["Days Since Edit", "Last Edited"],
        ascending=[False, False],
        na_position="last",
    )

    if (
        st.session_state.get("selected_category_type") == "pipeline_stage"
        and st.session_state.get("selected_pipeline_stage")
    ):
        st.info(f"Showing: {st.session_state['selected_pipeline_stage']}")

    overdue_count = int(display_df["Review Overdue"].sum()) if "Review Overdue" in display_df.columns else 0
    if overdue_count:
        st.warning(f"⚠️ {overdue_count} prospect(s) are overdue for principal review (>14 days).")

    # STEP 5: Gender and Grade filters - applied to display_df before search
    def _normalize_grade_value(value):
        if pd.isna(value):
            return ""
        return str(value).strip()

    # Apply Gender and Grade filters to display_df
    # Result goes to drill_down_df which feeds the search interface
    drill_down_df = display_df.copy()

    if selected_genders:
        drill_down_df = drill_down_df[drill_down_df["Gender"].isin(selected_genders)]

    if selected_grades:
        normalized_grades = drill_down_df[grade_col].apply(_normalize_grade_value)
        drill_down_df = drill_down_df[normalized_grades.isin(selected_grades)]

    drill_down_df_table = drill_down_df[table_cols]
    st.dataframe(
        drill_down_df_table,
        width="stretch",
        hide_index=True,
        column_config={
            "Notion URL": st.column_config.LinkColumn("Notion URL"),
            "Days Since Edit": st.column_config.NumberColumn("Days Since Edit"),
            "Days In Review": st.column_config.NumberColumn("Days In Review"),
            "Review Overdue": st.column_config.CheckboxColumn("Review Overdue"),
            "Last Edited": st.column_config.DatetimeColumn("Last Edited"),
        },
    )

    st.markdown('<div class="bhh-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="bhh-title">🎯 Student Detail & Actions</h3>', unsafe_allow_html=True)
    render_student_drawer()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### Actions")
    for _, row in drill_down_df.head(20).iterrows():
        action_cols = st.columns([3, 1])
        with action_cols[0]:
            st.markdown(f"{row['Name']} · {row['Pipeline Stage']} · {row['Status']}")
        with action_cols[1]:
            if st.button("Open", key=f"row_{row['_page_id']}", width="stretch"):
                open_student_drawer(row.to_dict(), source="table_actions")

    st.markdown("")

    # STEP 6: Search-first interface - runs on fully filtered drill_down_df
    # User types name → matches against drill_down_df → selects → triggers drill-down behavior
    st.markdown("#### Search")
    search_query = st.text_input("Search student or prospect", placeholder="Type name (e.g., John, Smith)").strip().lower()

    if search_query:
        # Split search by spaces for multi-word matching
        search_terms = search_query.split()

        # Filter candidates: match on Name (first or last name, case-insensitive)
        filtered_candidates = []
        for idx, (_, row) in enumerate(drill_down_df.iterrows()):
            name_lower = row["Name"].lower()
            # Check if all search terms are in the name
            if all(term in name_lower for term in search_terms):
                filtered_candidates.append((idx, row, name_lower))

        # Sort by whether the name *starts* with search terms (exact/prefix matches first)
        def sort_key(item):
            idx, row, name_lower = item
            # Prefer matches that start with the search query
            starts_with_score = 0 if name_lower.startswith(search_query) else 1
            # Secondary: prefer matches in the beginning of the string
            first_match_pos = name_lower.find(search_query)
            return (starts_with_score, first_match_pos if first_match_pos >= 0 else float('inf'))

        filtered_candidates.sort(key=sort_key)

        # Limit to 20 results
        filtered_candidates = filtered_candidates[:20]

        if filtered_candidates:
            # Create display names for selectbox
            candidate_names = [row["Name"] for _, row, _ in filtered_candidates]
            candidate_dict = {row["Name"]: (idx, row) for idx, row, _ in filtered_candidates}

            selected_name = st.selectbox("Select a student:", options=candidate_names, key="drill_down_select")

            if selected_name:
                idx, row = candidate_dict[selected_name]
                if st.button("Open selected student", key="open_selected_search_student", width="content"):
                    open_student_drawer(row.to_dict(), source="search")
        else:
            st.info("No results found.")
    else:
        st.caption("Start typing to search for a student or prospect...")

    # Render assessment UI: prefer centered modal overlay when available, otherwise fullscreen
    if st.session_state.assessment_modal_open and st.session_state.assessment_prospect:
        prospect_name, prospect_data = st.session_state.assessment_prospect
        if hasattr(st, "modal"):
            render_assessment_modal(prospect_name, prospect_data)
            return
        else:
            render_assessment_fullscreen(prospect_name, prospect_data)
            return


if __name__ == "__main__":
    main()