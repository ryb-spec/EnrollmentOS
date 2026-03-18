# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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


def apply_global_styles():
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(1200px 600px at 10% 10%, #eef2ff 0%, #f8fafc 40%, #ffffff 70%),
                        radial-gradient(900px 500px at 90% 20%, #e0f2fe 0%, #ffffff 55%);
        }
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='2' stitchTiles='stitch'/></filter><rect width='120' height='120' filter='url(%23n)' opacity='.08'/></svg>");
            opacity: 0.18;
            mix-blend-mode: multiply;
            pointer-events: none;
            z-index: 0;
        }
        .stApp::after {
            content: "";
            position: fixed;
            inset: -10%;
            background:
                radial-gradient(220px 220px at 15% 35%, rgba(59, 130, 246, 0.18), transparent 65%),
                radial-gradient(260px 260px at 85% 20%, rgba(14, 165, 233, 0.2), transparent 60%),
                radial-gradient(260px 260px at 70% 80%, rgba(147, 197, 253, 0.18), transparent 60%);
            filter: blur(2px);
            animation: floaty 18s ease-in-out infinite;
            pointer-events: none;
            z-index: 0;
        }
        @keyframes floaty {
            0% { transform: translateY(0px) translateX(0px); }
            50% { transform: translateY(12px) translateX(-8px); }
            100% { transform: translateY(0px) translateX(0px); }
        }
        section[data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.72);
            backdrop-filter: blur(12px);
        }
        .cc-header {
            font-size: 2.2rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-bottom: 0.4rem;
        }
        .cc-subtle {
            color: #667085;
        }
        .kpi-card {
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 14px;
            padding: 1rem 1.2rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(10px);
        }
        .kpi-label {
            font-size: 0.9rem;
            color: #667085;
        }
        .kpi-value {
            font-size: 1.9rem;
            font-weight: 700;
            color: #0f172a;
        }
        .goal-card {
            background: linear-gradient(160deg, rgba(255, 255, 255, 0.9), rgba(241, 245, 249, 0.6));
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 16px;
            padding: 1.2rem 1.4rem;
            box-shadow: 0 14px 36px rgba(15, 23, 42, 0.1);
            backdrop-filter: blur(12px);
        }
        .goal-label {
            font-size: 0.95rem;
            color: #64748b;
        }
        .goal-value {
            font-size: 2.4rem;
            font-weight: 700;
            color: #0f172a;
        }
        .status-badge {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 0.4rem;
            color: #0f172a;
            border: 1px solid rgba(148, 163, 184, 0.35);
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.55);
        }
        div.stButton > button {
            height: 4.8rem;
            white-space: pre-line;
            font-size: 1.1rem;
            line-height: 1.2;
            border-radius: 14px;
            border: 1px solid rgba(148, 163, 184, 0.28);
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            background: rgba(255, 255, 255, 0.78);
        }
        </style>
        
        """,
        unsafe_allow_html=True,
    )


# Compatibility wrappers for Streamlit query-param and rerun APIs
def _get_query_params():
    if hasattr(st, "experimental_get_query_params"):
        return st.experimental_get_query_params()
    if hasattr(st, "get_query_params"):
        return st.get_query_params()
    return {}


def _set_query_params(params=None):
    if params is None:
        params = {}
    if hasattr(st, "experimental_set_query_params"):
        try:
            st.experimental_set_query_params(**params)
        except TypeError:
            st.experimental_set_query_params(params)
        return
    if hasattr(st, "set_query_params"):
        st.set_query_params(**params)
        return


def _rerun():
    if hasattr(st, "experimental_rerun"):
        return st.experimental_rerun()
    if hasattr(st, "rerun"):
        return st.rerun()
    raise RuntimeError("Streamlit rerun not available in this version")


def load_pages():
    notion = notion_io.get_notion_client()
    return notion_io.fetch_all_pages_from_databases(notion, config.DATABASES)


def extract_files_links(props, prop_name):
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


def pages_to_df(pages, form_indexes):
    rows = []
    for page in pages:
        props = page.get("properties", {})
        name = extractors.get_title(props)

        raw_status = extractors.get_stage_value(props, config.PROP_STAGE)
        status = extractors.normalize_status(raw_status, page.get("_source", "(unknown)"), config)

        owners = extractors.get_multiselect_names(props, config.PROP_ASSIGNED)
        assigned = extractors.owners_str(owners)

        next_step = extractors.get_rich_text(props, config.PROP_NEXT_STEP) or ""
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

        # Assessment status tracking
        assessment_status = extractors.get_select_like_value(props, config.PROP_ASSESSMENT_STATUS) or ""
        assessment_date = extractors.get_rich_text(props, config.PROP_ASSESSMENT_DATE) or ""
        assessor_name = extractors.get_rich_text(props, config.PROP_ASSESSOR_NAME) or ""

        # Prospect needs assessment logic
        raw_status_lower = (raw_status or "").lower() if raw_status else ""
        is_reference_status = (
            status in getattr(config, "REFERENCE_STATUSES", set())
            or ("reference" in raw_status_lower and "princip" in raw_status_lower)
        )
        if is_reference_status:
            needs_assessment = assessment_status != "Completed"
        else:
            needs_assessment = form_summary["all_forms_submitted"] and assessment_status != "Completed" and assigned != "(unassigned)"

        # Determine if auto-prompt should trigger
        in_review = status in getattr(config, "ASSESSMENT_STATUSES", {"Prospect - In Review"})
        if is_reference_status:
            should_prompt_assessment = assessment_status != "Completed"
        else:
            should_prompt_assessment = in_review and assigned != "(unassigned)" and form_summary["all_forms_submitted"] and assessment_status != "Completed"

        parent_submission = form_summary["matches"].get("parent", {"submitted": False, "timestamp": ""})
        reference_1_submission = form_summary["matches"].get("reference_1", {"submitted": False, "timestamp": ""})
        reference_2_submission = form_summary["matches"].get("reference_2", {"submitted": False, "timestamp": ""})

        created_time = page.get("created_time", "")
        created = pd.to_datetime(created_time) if created_time else pd.NaT

        rows.append(
            {
                "Name": name,
                "Status": status,
                "Assigned Staff": assigned,
                "Next Step": next_step,
                "Days Since Edit": days_since_edit,
                "Last Edited": pd.to_datetime(last_edited) if last_edited else pd.NaT,
                "Created": created,
                "Notion URL": page.get("url", ""),
                "Source": page.get("_source", "(unknown)"),
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
                "Assessment Status": assessment_status,
                "Assessment Date": assessment_date,
                "Assessor Name": assessor_name,
                "Needs Assessment": needs_assessment,
                "Should Prompt Assessment": should_prompt_assessment,
                "_files": extract_files_links(props, FILES_PROPERTY_NAME),
                "_is_stale": is_stale,
                "_page_id": page.get("id", ""),
            }
        )

    # Build DataFrame from collected rows. Always return a DataFrame (empty if no rows).
    df = pd.DataFrame(rows)
    # Normalize expected columns when empty so downstream code can safely reference them
    if df.empty:
        expected_cols = [
            "Name",
            "Status",
            "Assigned Staff",
            "Next Step",
            "Days Since Edit",
            "Last Edited",
            "Created",
            "Notion URL",
            "Source",
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
            "Assessment Status",
            "Assessment Date",
            "Assessor Name",
            "Needs Assessment",
            "Should Prompt Assessment",
            "_files",
            "_is_stale",
            "_page_id",
        ]
        df = pd.DataFrame(columns=expected_cols)

    return df


def build_kpi_cards(items):
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{item["label"]}</div>
                    <div class="kpi-value">{item["value"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


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
            if st.button(f"{count}\n{status}", key=f"status_btn_{i}", use_container_width=True):
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
            elif division == "Legacy Division":
                rubric_data = rubric_components.render_legacy_rubric("assessment", initial_data)
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
            if st.button("✅ Submit Assessment", key="submit_assessment", use_container_width=True):
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
            if st.button("❌ Cancel", key="cancel_assessment", use_container_width=True):
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
        elif division == "Legacy Division":
            rubric_data = rubric_components.render_legacy_rubric("assessment", initial_data)
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
        if st.button("✅ Submit Assessment", key="submit_assessment_full", use_container_width=True):
            notion_result = assess_io.save_assessment_to_notion(prospect_name, payload, config)
            if notion_result.get("success"):
                st.success(f"✅ Assessment saved for {prospect_name}!")
                assess_io.export_assessment_to_drive(prospect_name, payload, folder_path=None)
                st.session_state.assessment_modal_open = False
                st.rerun()
            else:
                st.error(f"❌ Error saving assessment: {notion_result.get('message')}")

    with col2:
        if st.button("❌ Cancel", key="cancel_assessment_full", use_container_width=True):
            st.session_state.assessment_modal_open = False
            st.rerun()





def main():
    st.set_page_config(page_title="BHH Enrollment Command Center", layout="wide")
    apply_global_styles()

    st.markdown('<div class="cc-header">BHH Enrollment Command Center</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="cc-subtle">Live Notion view with enrollment progress and hygiene signals.</div>',
        unsafe_allow_html=True,
    )
    
    # Test reminder button in sidebar (only when email reminders enabled)
    with st.sidebar:
        st.markdown("---")
        st.subheader("⚙️ Admin Tools")
        if getattr(config, "EMAIL_ENABLED", False):
            if st.button("📧 Send Test Reminders Now", use_container_width=True):
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

    pages = load_pages()
    form_indexes = google_forms.load_google_form_indexes(config)

    form_errors = [f"{k}: {v.get('error')}" for k, v in form_indexes["forms"].items() if v.get("error")]
    if form_errors:
        st.warning("Google Forms source warning (using fallback or no data): " + " | ".join(form_errors))

    df = pages_to_df(pages, form_indexes)

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

    if "selected_status" not in st.session_state:
        st.session_state.selected_status = "All"
    if "selected_source" not in st.session_state:
        st.session_state.selected_source = "All"
    if "assessment_modal_open" not in st.session_state:
        st.session_state.assessment_modal_open = False
    if "assessment_prospect" not in st.session_state:
        st.session_state.assessment_prospect = None

    source_options = ["All"] + [label for label, _ in config.DATABASES]
    st.markdown("")
    st.selectbox("Source", source_options, key="selected_source")

    base_df = df.copy()
    if st.session_state.selected_source != "All":
        base_df = base_df[base_df["Source"] == st.session_state.selected_source]

    total_count = len(base_df)
    missing_assigned = (base_df["Assigned Staff"] == "(unassigned)").sum()
    missing_next_step = (base_df["Next Step"] == "").sum()
    missing_form_packet = (~base_df["All Forms Submitted"]).sum()
    # Safely compute needs_assessment_count if the column exists
    if "Needs Assessment" in base_df.columns:
        needs_assessment_count = int(base_df["Needs Assessment"].sum())
    else:
        needs_assessment_count = 0
    stale_count = base_df["_is_stale"].sum()

    # Check for pending assessments that should auto-prompt
    pending_assessments = base_df[base_df["Should Prompt Assessment"]]
    if len(pending_assessments) > 0 and not st.session_state.assessment_modal_open:
        # Show banner about pending assessments
        st.warning(f"⏰ **{len(pending_assessments)} assessments pending!** Click 'Complete Assessment' to begin.")
        # Provide a quick-action list so staff can open the rubric without expanding rows
        st.markdown("#### Pending Assessments - Quick Actions")
        for pidx, (_, prow) in enumerate(pending_assessments.iterrows()):
            cols = st.columns([5, 1])
            with cols[0]:
                st.markdown(f"**{prow['Name']}** - {prow['Status']} - {prow['Assigned Staff']}")
            with cols[1]:
                btn_key = f"quick_complete_{pidx}"
                if st.button("✏️ Complete", key=btn_key):
                    # Open modal at top-level by setting session state and re-running
                    st.session_state.assessment_modal_open = True
                    st.session_state.assessment_prospect = (prow['Name'], prow.to_dict())
                    st.rerun()
                # Open in new tab link
                new_tab_url = f"?assessment=1&name={quote_plus(prow['Name'])}"
                st.markdown(f"<a href=\"{new_tab_url}\" target=\"_blank\">Open in new tab</a>", unsafe_allow_html=True)
        # Convenience: open the first pending assessment directly
        if len(pending_assessments) > 0:
            if st.button("Open first pending assessment", key="open_first_pending"):
                first = pending_assessments.iloc[0]
                st.session_state.assessment_modal_open = True
                st.session_state.assessment_prospect = (first['Name'], first.to_dict())

    # -----------------------------
    # PROJECTION + KPI LOGIC
    # Rule: All students in Reenrollment DB count as 95% unless marked retention risk.
    # Separate display for new enrollment vs re-enrollment
    # -----------------------------
    prospects_df = base_df[base_df["Source"] != config.REENROLLMENT_SOURCE_LABEL]
    reenrollment_df = base_df[base_df["Source"] == config.REENROLLMENT_SOURCE_LABEL]

    enrolled_prospects = prospects_df["Status"].isin(config.ENROLLED_STATUSES).sum()
    prospect_in_review = prospects_df["Status"].isin(getattr(config, "ASSESSMENT_STATUSES", {"Prospect - In Review"})).sum()

    retention_risk_count = reenrollment_df["Status"].isin(config.RETENTION_RISK_STATUSES).sum()

    reenrollment_total = len(reenrollment_df)
    reenrollment_non_risk = max(reenrollment_total - retention_risk_count, 0)

    projected_total = enrolled_prospects + (reenrollment_non_risk * config.REENROLLMENT_PROJECTION_RATE)

    # Keep "Current Enrolled" as enrolled prospects (new students) so the label stays honest.
    current_enrolled = int(enrolled_prospects)

    percent_complete = 0 if ENROLLMENT_GOAL == 0 else projected_total / ENROLLMENT_GOAL
    remaining = max(ENROLLMENT_GOAL - projected_total, 0)

    st.markdown("")
    
    # Enrollment Snapshot - New Prospects Only
    st.subheader("Enrollment Snapshot")
    
    # Calculate metrics for new prospects only (exclude re-enrollment)
    prospects_only_df = prospects_df.copy()
    
    # Total inquiries this year
    current_year = pd.Timestamp.now().year
    prospects_with_created = prospects_only_df["Created"].notna()
    if prospects_with_created.any():
        inquiries_this_year = (
            prospects_only_df[prospects_with_created]["Created"].dt.year == current_year
        ).sum()
    else:
        # Fallback: count all prospects if Created is missing
        inquiries_this_year = len(prospects_only_df)
    
    # Rejected / Not a good fit
    rejected_statuses = {"Application On Pause", "Not a Good Fit"}
    rejected_count = prospects_only_df["Status"].isin(rejected_statuses).sum()
    
    # Stage 1 – Early contact
    stage1_statuses = {"Tried to Contact", "Intake Sent", "Not Started"}
    stage1_count = prospects_only_df["Status"].isin(stage1_statuses).sum()
    
    # Stage 2 – In review
    stage2_statuses = {"Prospect - In Review"}
    stage2_count = prospects_only_df["Status"].isin(stage2_statuses).sum()
    
    # Stage 3 – Application sent
    stage3_statuses = {"Application Sent", "Application Sent to Fill Out"}
    stage3_count = prospects_only_df["Status"].isin(stage3_statuses).sum()
    
    # Stage 4 – Application completed
    stage4_statuses = {"Application Completed", "Application Completed Awaiting Final Decision", "Awaiting Final Decision"}
    stage4_count = prospects_only_df["Status"].isin(stage4_statuses).sum()
    
    # Display snapshot KPIs
    build_kpi_cards(
        [
            {"label": "Total inquiries this year", "value": int(inquiries_this_year)},
            {"label": "Rejected / not a good fit", "value": int(rejected_count)},
            {"label": "Stage 1 – Early contact", "value": int(stage1_count)},
            {"label": "Stage 2 – In review", "value": int(stage2_count)},
            {"label": "Stage 3 – Application sent", "value": int(stage3_count)},
            {"label": "Stage 4 – Application completed", "value": int(stage4_count)},
        ]
    )
    
    # Separate enrollment display: New vs Re-enrollment (below snapshot)
    st.markdown("")
    enrollment_cols = st.columns(4)
    with enrollment_cols[0]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">New Enrolled</div>
                <div class="kpi-value">{current_enrolled}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with enrollment_cols[1]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Re-enrollment (Non-Risk)</div>
                <div class="kpi-value">{int(reenrollment_non_risk)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with enrollment_cols[2]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Re-enrollment Risk</div>
                <div class="kpi-value">{retention_risk_count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with enrollment_cols[3]:
        projected_display = f"{projected_total:.1f}/{ENROLLMENT_GOAL}"

        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Total Enrolled (Proj.)</div>
                <div class="kpi-value">{projected_display}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    # Enrollment goal progress
    st.markdown("")
    goal_cols = st.columns([2, 3])
    with goal_cols[0]:
        st.markdown(
        f"""
        <div class="goal-card">
            <div class="goal-label">Progress to Goal</div>
            <div class="goal-value">{percent_complete:.0%}</div>
            <div class="goal-label">Remaining: {remaining}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with goal_cols[1]:
        st.markdown('<div class="goal-label">Goal Progress</div>', unsafe_allow_html=True)
        st.progress(min(max(percent_complete, 0.0), 1.0))

    st.markdown("")
    build_kpi_cards(
        [
            {"label": "Prospect - In Review", "value": prospect_in_review},
            {"label": "Reenrollment Total", "value": reenrollment_total},
            {"label": "Reenrollment Retention Risk", "value": retention_risk_count},
            {"label": "Total Applications", "value": total_count},
            {"label": f"Missing {config.PROP_ASSIGNED}", "value": missing_assigned},
            {"label": f"Missing {config.PROP_NEXT_STEP}", "value": missing_next_step},
            {"label": f"Stale >= {config.STALE_DAYS} days", "value": stale_count},
            {"label": "Incomplete Form Packet", "value": missing_form_packet},
            {"label": "Ready for Assessment", "value": needs_assessment_count},
        ]
    )

    st.subheader(f"{config.PROP_STAGE} Overview")

    status_counts_series = base_df["Status"].value_counts()
    hidden = getattr(config, "HIDE_STATUS_CARDS", set())
    status_counts = [(s, int(c)) for s, c in status_counts_series.items() if s not in hidden]

    active_total = int(
        (~base_df["Status"].isin(getattr(config, "CLOSED_PROSPECT_STATUSES", {"Prospect - Closed"}))).sum()
    )
    build_status_cards(status_counts, active_total)

    st.caption(f"Selected {config.PROP_STAGE}: {st.session_state.selected_status}")

    # Initialize filtered DataFrame from base and apply status selector
    df_filtered = base_df.copy()
    if st.session_state.selected_status != "All":
        df_filtered = df_filtered[df_filtered["Status"] == st.session_state.selected_status]

    filter_cols = st.columns(6)
    stale_only = filter_cols[0].checkbox("Stale only", value=False)
    unassigned_only = filter_cols[1].checkbox("Unassigned only", value=False)
    missing_next_step_only = filter_cols[2].checkbox("Missing Next Step only", value=False)
    incomplete_packet_only = filter_cols[3].checkbox("Incomplete forms only", value=False)
    needs_rubric_only = filter_cols[4].checkbox("Needs BHH rubric", value=False)
    needs_assessment_only = filter_cols[5].checkbox("Needs Assessment", value=False)
    if unassigned_only:
        df_filtered = df_filtered[df_filtered["Assigned Staff"] == "(unassigned)"]
    if missing_next_step_only:
        df_filtered = df_filtered[df_filtered["Next Step"] == ""]
    if incomplete_packet_only:
        df_filtered = df_filtered[~df_filtered["All Forms Submitted"]]
    if needs_rubric_only:
        df_filtered = df_filtered[df_filtered["Needs BHH Rubric"]]
    if needs_assessment_only:
        # Use get with a default Series(False) to avoid KeyError when column missing
        df_filtered = df_filtered[df_filtered.get("Needs Assessment", pd.Series(False, index=df_filtered.index))]

    table_cols = [
        "Name",
        "Source",
        "Status",
        "Assigned Staff",
        "Next Step",
        "Days Since Edit",
        "Last Edited",
        "All Forms Submitted",
        "Packet Score",
        "Packet Max",
        "Packet %",
        "Assessment Status",
        "Assessment Date",
        "Assessor Name",
        "BHH Rubric Score",
        "BHH Rubric Status",
        "Parent Form Submitted",
        "Parent Form Timestamp",
        "Reference 1 Submitted",
        "Reference 1 Timestamp",
        "Reference 2 Submitted",
        "Reference 2 Timestamp",
        "Notion URL",
    ]
    display_df = df_filtered[table_cols + ["_files", "_page_id"]].sort_values(
        by=["Days Since Edit", "Last Edited"],
        ascending=[False, False],
        na_position="last",
    )
    display_df_table = display_df[table_cols]

    st.dataframe(
        display_df_table,
    use_container_width=True,
        hide_index=True,
        column_config={
            "Notion URL": st.column_config.LinkColumn("Notion URL"),
            "Days Since Edit": st.column_config.NumberColumn("Days Since Edit"),
            "Last Edited": st.column_config.DatetimeColumn("Last Edited"),
            "Assessment Status": st.column_config.TextColumn("Assessment Status"),
            "Assessment Date": st.column_config.TextColumn("Assessment Date"),
        },
    )

    st.markdown("")
    st.subheader("Student Drill-Down & Actions")
    
    # Search-first interface
    search_query = st.text_input("Search student or prospect", placeholder="Type name (e.g., John, Smith)").strip().lower()
    
    if search_query:
        # Split search by spaces for multi-word matching
        search_terms = search_query.split()
        
        # Filter candidates: match on Name (first or last name, case-insensitive)
        filtered_candidates = []
        for idx, (_, row) in enumerate(display_df.iterrows()):
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
                
                # Render the selected student's details (same as before)
                title = f"{row['Name']} - {row['Status']}"
                st.markdown(f"### {title}")
                
                st.markdown(f"**Assigned Staff:** {row['Assigned Staff']}")
                st.markdown(f"**Last Edited:** {row['Last Edited']}")
                st.markdown(
                    f"**Form Packet Score:** {int(row['Packet Score'])}/{int(row['Packet Max'])} ({row['Packet %']:.0%})"
                )
                
                # Assessment status display
                st.markdown("#### Assessment Status")
                if row["Assessment Status"] == "Completed":
                    st.markdown(f"✅ **Completed** on {row['Assessment Date']} by {row['Assessor Name']}")
                    if st.button("📝 Revise Assessment", key=f"revise_assess_{idx}", use_container_width=True):
                        st.session_state.assessment_modal_open = True
                        st.session_state.assessment_prospect = (row["Name"], row.to_dict())
                        st.rerun()
                else:
                    st.markdown("⏳ **Not yet completed**")
                    if row.get("Needs Assessment", False):
                        if st.button("✏️ Complete Assessment", key=f"complete_assess_{idx}", use_container_width=True):
                            st.session_state.assessment_modal_open = True
                            st.session_state.assessment_prospect = (row["Name"], row.to_dict())
                            st.rerun()
                        new_tab_url = f"?assessment=1&name={quote_plus(row['Name'])}"
                        st.markdown(f"<a href=\"{new_tab_url}\" target=\"_blank\">Open in new tab</a>", unsafe_allow_html=True)
                
                st.divider()
                
                if pd.notna(row["BHH Rubric Score"]):
                    st.markdown(f"**BHH Rubric Score:** {row['BHH Rubric Score']}")
                else:
                    st.markdown("**BHH Rubric Score:** Not entered yet")
                if row["BHH Rubric Status"]:
                    st.markdown(f"**BHH Rubric Status:** {row['BHH Rubric Status']}")

                st.markdown("**Parent Form:** " + ("✅ Submitted" if row["Parent Form Submitted"] else "❌ Missing"))
                if row["Parent Form Timestamp"]:
                    st.markdown(f"- Parent timestamp: {row['Parent Form Timestamp']}")

                st.markdown("**Reference 1:** " + ("✅ Submitted" if row["Reference 1 Submitted"] else "❌ Missing"))
                if row["Reference 1 Timestamp"]:
                    st.markdown(f"- Ref 1 timestamp: {row['Reference 1 Timestamp']}")

                st.markdown("**Reference 2:** " + ("✅ Submitted" if row["Reference 2 Submitted"] else "❌ Missing"))
                if row["Reference 2 Timestamp"]:
                    st.markdown(f"- Ref 2 timestamp: {row['Reference 2 Timestamp']}")

                st.markdown("**Notion Page:**")
                st.link_button("Open in Notion", row["Notion URL"])

                files = row["_files"]
                if files:
                    st.markdown("**Documents:**")
                    for f in files:
                        st.markdown(f"- [{f['name']}]({f['url']})")
                else:
                    st.markdown("**Documents:** None found")
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