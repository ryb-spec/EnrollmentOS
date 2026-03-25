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
from datetime import datetime, timedelta

import config
import extractors
import notion_io
import google_forms

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

FOLLOW_UP_DAYS_THRESHOLD = 2  # Days since last activity to trigger follow-up
STUCK_DAYS_THRESHOLD = 7      # Days with no movement to flag as stuck

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

# Stage-specific overdue thresholds (days)
STAGE_OVERDUE_RULES = {
    "Stage 2 - Principal Review": 14,
    "Stage 3 - Application": 10,
    "Stage 4 - Interview": 7,
}

# Reenrollment status mapping
REENROLLMENT_STATUS_MAP = {
    "Confirmed": "Confirmed",
    "In Progress": "In Progress",
    "At Risk": "At Risk",
    "Not Returning": "Not Returning",
}

# Reenrollment projection weights
REENROLLMENT_WEIGHTS = {
    "Confirmed": 0.95,
    "In Progress": 0.95,
    "At Risk": 0.50,
    "Not Returning": 0.00,
}

# Stage-specific conversion rates to enrollment
STAGE_CONVERSION_RATES = {
    "Lead": 0.20,                          # 20% of leads become enrolled
    "Stage 1 - Intake": 0.50,              # 50% conversion
    "Stage 2 - Principal Review": 0.65,    # 65% conversion
    "Stage 3 - Application": 0.85,         # 85% conversion
    "Stage 4 - Interview": 0.85,           # 85% conversion
    "Stage 5 - Decision": 1.00,            # 100% (already enrolled)
}

ENROLLMENT_GOAL = 102


# ============================================================================
# STYLING
# ============================================================================

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
            max-width: 1400px;
            margin: 0 auto;
            padding-top: 12px;
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
            padding: 20px;
            text-align: center;
            border-top: 4px solid #3B82F6;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .kpi-card:hover {
            box-shadow: 0 4px 6px rgba(0,0,0,.15);
            transform: translateY(-2px);
        }
        .kpi-number {
            font-size: 2.5em;
            font-weight: 700;
            color: #111827;
        }
        .kpi-label {
            font-size: 0.85em;
            color: #6B7280;
            margin-top: 8px;
            font-weight: 500;
        }
        /* Color indicators */
        .status-red {
            background-color: #FEE2E2;
            border-left: 4px solid #DC2626;
            padding: 12px;
            border-radius: 4px;
        }
        .status-yellow {
            background-color: #FEF3C7;
            border-left: 4px solid #F59E0B;
            padding: 12px;
            border-radius: 4px;
        }
        .status-green {
            background-color: #DCFCE7;
            border-left: 4px solid #16A34A;
            padding: 12px;
            border-radius: 4px;
        }
        .badge-red { background: #FEE2E2; color: #991B1B; border: 1px solid #FECACA; }
        .badge-yellow { background: #FEF3C7; color: #92400E; border: 1px solid #FDE047; }
        .badge-green { background: #DCFCE7; color: #166534; border: 1px solid #BBF7D0; }
        
        [data-testid="stDataFrame"] thead tr th {
            background-color: #374151 !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
        }
        [data-testid="stDataFrame"] tbody tr:nth-child(even) {
            background-color: #F9FAFB !important;
        }
        [data-testid="stDataFrame"] tbody tr:hover {
            background-color: #F3F4F6 !important;
        }
        
        div.stButton > button {
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        div.stButton > button:hover {
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _rerun():
    if hasattr(st, "rerun"):
        return st.rerun()
    if hasattr(st, "experimental_rerun"):
        return st.experimental_rerun()


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


# ============================================================================
# DATA EXTRACTION & TRANSFORMATION
# ============================================================================

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
    
    # Case-insensitive fallback
    status_lower = status_text.lower()
    for key, stage in PIPELINE_STAGE_MAPPING.items():
        if key.lower() == status_lower:
            return stage
    
    return "UNKNOWN"


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


def calculate_days_since_activity(row) -> int:
    """Calculate days since last activity (edited or contacted)."""
    last_edited = row.get("Last Edited")
    last_contacted = row.get("Last Contacted")
    
    def _to_datetime(val):
        if pd.isna(val):
            return None
        try:
            dt = pd.to_datetime(val, errors="coerce")
            if pd.notna(dt):
                # Strip timezone info to make timezone-naive
                if hasattr(dt, 'tz_localize'):
                    dt = dt.tz_localize(None)
                elif dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                return dt
            return None
        except:
            return None
    
    dt_edited = _to_datetime(last_edited)
    dt_contacted = _to_datetime(last_contacted)
    
    # Use the most recent activity
    if dt_edited and dt_contacted:
        last = max(dt_edited, dt_contacted)
    elif dt_edited:
        last = dt_edited
    elif dt_contacted:
        last = dt_contacted
    else:
        return None
    
    # Use timezone-naive now() for comparison
    now = pd.Timestamp.now().tz_localize(None) if pd.Timestamp.now().tzinfo else pd.Timestamp.now()
    days = (now - last).days
    return days


def is_follow_up_needed(row) -> bool:
    """
    Check if student needs follow-up:
    - Next Step is NOT empty
    - AND days since activity >= threshold
    """
    next_step = str(row.get("Next Step", "")).strip()
    if not next_step:
        return False
    
    days_since = calculate_days_since_activity(row)
    return days_since is not None and days_since >= FOLLOW_UP_DAYS_THRESHOLD


def is_stuck_or_overdue(row) -> dict:
    """
    Check if student is STUCK or OVERDUE.
    Returns: dict with keys: is_flagged, flag_type, days_in_stage
    """
    days_since = calculate_days_since_activity(row)
    
    if days_since is None:
        return {"is_flagged": False, "flag_type": "", "days_in_stage": None}
    
    stage = str(row.get("Pipeline Stage", "")).strip()
    
    # Check stage-specific overdue rule first
    if stage in STAGE_OVERDUE_RULES:
        max_days = STAGE_OVERDUE_RULES[stage]
        if days_since > max_days:
            return {"is_flagged": True, "flag_type": "🔴 OVERDUE", "days_in_stage": days_since}
    
    # Check general stuck rule
    if days_since >= STUCK_DAYS_THRESHOLD:
        return {"is_flagged": True, "flag_type": "⚠️ STUCK", "days_in_stage": days_since}
    
    return {"is_flagged": False, "flag_type": "", "days_in_stage": days_since}


def classify_reenrollment_status(status_text: str) -> str:
    """Classify reenrollment status into simplified buckets."""
    if not status_text:
        return "Unknown"
    
    status_lower = str(status_text).lower()
    
    # Direct classification
    for key, bucket in REENROLLMENT_STATUS_MAP.items():
        if key.lower() == status_lower:
            return bucket
    
    # Pattern matching
    if any(x in status_lower for x in ["confirmed", "committed"]):
        return "Confirmed"
    if any(x in status_lower for x in ["returning", "enrolled", "active"]):
        return "In Progress"
    if any(x in status_lower for x in ["at risk", "uncertain", "maybe"]):
        return "At Risk"
    if any(x in status_lower for x in ["not returning", "withdrawn", "declined", "no"]):
        return "Not Returning"
    
    return "In Progress"


def pages_to_df(pages, form_indexes):
    """Convert Notion pages to simplified DataFrame."""
    rows = []
    
    for page in pages:
        props = page.get("properties", {})
        name = extractors.get_title(props)
        
        # Helper functions from original
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
        
        # Core fields
        source = _first_select_like("Source") or _first_text_like("Source") or page.get("_source", "(unknown)")
        status = _first_select_like("Status") or ""
        
        # Map to pipeline stage
        pipeline_stage = map_status_to_stage(status)
        
        # Skip excluded records
        if pipeline_stage == "EXCLUDE":
            continue
        if source != config.REENROLLMENT_SOURCE_LABEL and pipeline_stage == "EXCLUDE":
            continue
        
        # Assigned staff (only for new prospects)
        if source == config.REENROLLMENT_SOURCE_LABEL:
            assigned = ""
        else:
            owners = extractors.get_multiselect_names(props, config.PROP_ASSIGNED)
            assigned = extractors.owners_str(owners) if owners else "(unassigned)"
        
        # Dates
        last_edited = page.get("last_edited_time", "")
        last_edited_dt = pd.to_datetime(last_edited) if last_edited else pd.NaT
        last_contacted_dt = _first_date_like("Last Contacted")
        created_dt = page.get("created_time", "")
        created_dt = pd.to_datetime(created_dt) if created_dt else pd.NaT
        
        # Contact info
        parent_1_name = _first_text_like("Parent 1 Name")
        parent_1_email = ""
        parent_1_phone = ""
        
        # Other fields
        gender = _first_select_like("Gender")
        grade = _first_select_like("Entering Grade")
        track = _first_select_like("Track")
        target_school_year = _first_select_like("Target School Year")
        notes = _first_text_like("Notes")
        
        row = {
            "Name": name,
            "Source": source,
            "Status": status,
            "Pipeline Stage": pipeline_stage,
            "Assigned Staff": assigned,
            "Track": track,
            "Target School Year": target_school_year,
            "Gender": gender,
            "Grade": grade,
            "Last Edited": last_edited_dt,
            "Last Contacted": last_contacted_dt,
            "Created": created_dt,
            "Parent 1 Name": parent_1_name,
            "Parent 1 Email": parent_1_email,
            "Parent 1 Phone": parent_1_phone,
            "Notes": notes,
            "Notion URL": page.get("url", ""),
            "_files": extract_files_links(props, "Files & media"),
            "_page_id": page.get("id", ""),
        }
        
        # Compute next step
        row["Next Step"] = compute_next_step(row)
        
        rows.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    if not df.empty:
        # Add computed columns
        df["Days Since Activity"] = df.apply(calculate_days_since_activity, axis=1)
        df["Needs Follow-Up"] = df.apply(is_follow_up_needed, axis=1)
        
        # Add stuck/overdue info
        stuck_data = df.apply(is_stuck_or_overdue, axis=1)
        df["Is Stuck Or Overdue"] = stuck_data.apply(lambda x: x["is_flagged"])
        df["Flag Type"] = stuck_data.apply(lambda x: x["flag_type"])
        df["Days In Stage"] = stuck_data.apply(lambda x: x["days_in_stage"])
    
    return df


# ============================================================================
# MAIN DASHBOARD
# ============================================================================

def main():
    st.set_page_config(page_title="Enrollment Dashboard", layout="wide", initial_sidebar_state="collapsed")
    apply_global_styles()
    
    st.title("📊 Enrollment Action Dashboard")
    st.markdown("*Focus: Follow-up today + Stuck/Overdue students*")
    st.divider()
    
    # Load data
    try:
        df, form_indexes, total_pages = get_normalized_dataset()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return
    
    if df.empty:
        st.warning("No active prospects found.")
        return
    
    # Filter by source
    view_tab1, view_tab2 = st.tabs(["📋 New Prospects", "🔄 Reenrollment"])
    
    with view_tab1:
        # Filter to New Prospects only
        prospects_df = df[df["Source"] != config.REENROLLMENT_SOURCE_LABEL].copy()
        
        if prospects_df.empty:
            st.info("No new prospects at this time.")
        else:
            render_action_view(prospects_df, "New Prospects")
    
    with view_tab2:
        # Filter to Reenrollment only
        reenrollment_df = df[df["Source"] == config.REENROLLMENT_SOURCE_LABEL].copy()
        
        if reenrollment_df.empty:
            st.info("No reenrollment records at this time.")
        else:
            render_reenrollment_view(reenrollment_df)


def render_action_view(df: pd.DataFrame, source_label: str):
    """Render the main action dashboard for new prospects."""
    
    # Calculate KPIs
    total_active = len(df)
    follow_up_needed = df[df["Needs Follow-Up"]].copy()
    stuck_overdue = df[df["Is Stuck Or Overdue"]].copy()
    enrolled = df[df["Pipeline Stage"] == "Stage 5 - Decision"]
    
    # Calculate projected enrollment based on conversion rates
    projected_total = 0
    for stage, conversion_rate in STAGE_CONVERSION_RATES.items():
        students_in_stage = len(df[df["Pipeline Stage"] == stage])
        projected_from_stage = students_in_stage * conversion_rate
        projected_total += projected_from_stage
    
    # Show enrollment goal and progress
    st.markdown("### 🎯 Enrollment Goal Progress")
    enrollment_goal = ENROLLMENT_GOAL
    enrolled_count = len(enrolled)
    progress_pct = (enrolled_count / enrollment_goal * 100)
    projected_pct = (projected_total / enrollment_goal * 100)
    
    goal_col1, goal_col2, goal_col3, goal_col4 = st.columns(4)
    with goal_col1:
        st.metric("Enrolled (Actual)", f"{enrolled_count}", f"Goal: {enrollment_goal}")
    with goal_col2:
        st.metric("Projected Enrollment", f"{projected_total:.1f}", 
                 f"{projected_pct:.0f}% of goal")
    with goal_col3:
        st.metric("Enrollment Gap", f"{enrollment_goal - enrolled_count}", 
                 f"{progress_pct:.0f}% actual")
    with goal_col4:
        st.metric("Additional Needed", max(0, round(enrollment_goal - projected_total)), 
                 f"from current pipeline")
    
    # Show actual vs projected progress bars
    st.markdown("**Actual Enrollment Progress**")
    st.progress(min(progress_pct / 100, 1.0))
    
    st.markdown("**Projected Enrollment Progress** (with conversion rates)")
    st.progress(min(projected_pct / 100, 1.0))
    
    st.divider()
    
    # Show the 5 enrollment stages
    st.markdown("### 📍 The 5 Enrollment Stages")
    
    stages = {
        "Lead": {
            "description": "Initial contact made",
            "status_list": ["New Lead", "Contacted"],
            "color": "🔵"
        },
        "Stage 1 - Intake": {
            "description": "Application packet & references gathering",
            "status_list": ["Intake Sent", "Gathering References"],
            "color": "🟡"
        },
        "Stage 2 - Principal Review": {
            "description": "Principal assessment (max 14 days)",
            "status_list": ["Under Principal Review"],
            "color": "🟠"
        },
        "Stage 3 - Application": {
            "description": "Application submission & completion",
            "status_list": ["Application Sent", "Application Started"],
            "color": "🟣"
        },
        "Stage 4 - Interview": {
            "description": "Interview scheduling & completion",
            "status_list": ["Application Completed", "Scheduling Interview"],
            "color": "🔴"
        },
        "Stage 5 - Decision": {
            "description": "Enrollment complete ✅",
            "status_list": ["Accepted", "Enrolled"],
            "color": "🟢"
        },
    }
    
    # Show stage breakdown
    stage_cols = st.columns(6)
    for idx, (stage_name, stage_info) in enumerate(stages.items()):
        if idx < 6:
            with stage_cols[idx]:
                # Count students in this stage
                stage_count = len(df[df["Pipeline Stage"] == stage_name])
                st.markdown(f"""
                <div style="background:#f0f2f6;padding:12px;border-radius:8px;text-align:center;">
                    <div style="font-size:1.5em;margin-bottom:4px;">{stage_info['color']}</div>
                    <div style="font-weight:700;font-size:0.9em;">{stage_name}</div>
                    <div style="font-size:0.75em;color:#666;margin:4px 0;">{stage_info['description']}</div>
                    <div style="font-size:1.5em;font-weight:700;color:#111;">{stage_count}</div>
                    <div style="font-size:0.7em;color:#999;">students</div>
                </div>
                """, unsafe_allow_html=True)
                # Show conversion rate
                conversion_rate = STAGE_CONVERSION_RATES.get(stage_name, 0)
                st.markdown(f"**Conversion:** {conversion_rate*100:.0f}%", help=f"Estimated conversion rate through this stage")
    st.divider()
    
    # KPI Cards
    st.subheader("📈 Action Metrics")
    kpi_cols = st.columns(4)
    
    with kpi_cols[0]:
        st.metric("Total Active", len(df))
    
    with kpi_cols[1]:
        st.metric("Follow-Up Today", len(follow_up_needed), f"{len(follow_up_needed) / max(len(df), 1) * 100:.0f}%")
    
    with kpi_cols[2]:
        st.metric("Stuck / Overdue", len(stuck_overdue), f"{len(stuck_overdue) / max(len(df), 1) * 100:.0f}%")
    
    with kpi_cols[3]:
        st.metric("Enrolled", len(enrolled))
    
    st.divider()
    
    # Toggle for view - use session state
    if "action_view_choice" not in st.session_state:
        st.session_state.action_view_choice = "all"
    
    col1, col2, col3 = st.columns(3)
    
    if col1.button("📞 Follow-Up Today", use_container_width=True, key="btn_followup"):
        st.session_state.action_view_choice = "follow_up"
    if col2.button("⚠️ Stuck / Overdue", use_container_width=True, key="btn_stuck"):
        st.session_state.action_view_choice = "stuck"
    if col3.button("📋 All Active", use_container_width=True, key="btn_all"):
        st.session_state.action_view_choice = "all"
    
    view_choice = st.session_state.action_view_choice
    
    # Column selection for display
    display_columns = ["Name", "Pipeline Stage", "Assigned Staff", "Next Step", "Days Since Activity"]
    
    # Apply view filter
    if view_choice == "follow_up":
        display_df = follow_up_needed[display_columns].copy()
        st.subheader("📞 Follow-Up Needed Today")
        if display_df.empty:
            st.success("✅ No follow-ups needed today!")
        else:
            # Sort by days since activity (longest first)
            display_df = display_df.sort_values("Days Since Activity", ascending=False, na_position="last")
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    elif view_choice == "stuck":
        display_df = stuck_overdue.copy()
        st.subheader("⚠️ Stuck / Overdue Students")
        
        # Show with flag type
        show_cols = ["Name", "Pipeline Stage", "Assigned Staff", "Flag Type", "Days In Stage"]
        show_cols = [c for c in show_cols if c in display_df.columns]
        if show_cols:
            display_df_show = display_df[show_cols].copy()
            st.dataframe(display_df_show, use_container_width=True, hide_index=True)
        else:
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    else:  # all
        st.subheader("📋 All Active Prospects")
        display_df = df[display_columns].copy()
        display_df = display_df.sort_values("Days Since Activity", ascending=False, na_position="last")
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_reenrollment_view(df: pd.DataFrame):
    """Render reenrollment dashboard with projection."""
    
    st.subheader("🔄 Reenrollment Pipeline")
    
    # Classify status
    df["Reenrollment Status"] = df["Status"].apply(classify_reenrollment_status)
    
    # Calculate projections
    confirmed_count = len(df[df["Reenrollment Status"] == "Confirmed"])
    in_progress_count = len(df[df["Reenrollment Status"] == "In Progress"])
    at_risk_count = len(df[df["Reenrollment Status"] == "At Risk"])
    not_returning_count = len(df[df["Reenrollment Status"] == "Not Returning"])
    
    # Calculate weighted projection
    projected_confirmed = confirmed_count * REENROLLMENT_WEIGHTS["Confirmed"]
    projected_in_progress = in_progress_count * REENROLLMENT_WEIGHTS["In Progress"]
    projected_at_risk = at_risk_count * REENROLLMENT_WEIGHTS["At Risk"]
    projected_total = projected_confirmed + projected_in_progress + projected_at_risk
    
    # Display KPIs
    kpi_cols = st.columns(5)
    
    with kpi_cols[0]:
        st.metric("Confirmed", confirmed_count)
    
    with kpi_cols[1]:
        st.metric("In Progress", in_progress_count)
    
    with kpi_cols[2]:
        st.metric("At Risk", at_risk_count)
    
    with kpi_cols[3]:
        st.metric("Not Returning", not_returning_count)
    
    with kpi_cols[4]:
        st.metric("Projected Returning", f"{projected_total:.0f}")
    
    st.divider()
    
    # Reenrollment table
    display_cols = ["Name", "Status", "Reenrollment Status"]
    display_df = df[display_cols].copy() if set(display_cols).issubset(df.columns) else df
    st.dataframe(display_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
