import pandas as pd
import streamlit as st

import config
import extractors
import notion_io

ENROLLMENT_GOAL = 102
# Adjust to match your actual "enrolled" statuses.
ENROLLED_STATUSES = {"Enrolled", "Accepted", "Active"}
FILES_PROPERTY_NAME = "Files & media"


def load_pages():
    notion = notion_io.get_notion_client()
    return notion_io.fetch_all_pages_from_databases(notion, config.DATABASES)


def pages_to_df(pages):
    rows = []
    for page in pages:
        props = page.get("properties", {})
        name = extractors.get_title(props)
        status = extractors.get_stage_value(props, config.PROP_STAGE)
        if not status:
            status = f"(No {config.PROP_STAGE})"

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

        rows.append(
            {
                "Name": name,
                "Status": status,
                "Assigned Staff": assigned,
                "Next Step": next_step,
                "Days Since Edit": days_since_edit,
                "Last Edited": pd.to_datetime(last_edited) if last_edited else pd.NaT,
                "Notion URL": page.get("url", ""),
                "Source": page.get("_source", "(unknown)"),
                "_files": extract_files_links(props, FILES_PROPERTY_NAME),
                "_is_stale": is_stale,
            }
        )
    return pd.DataFrame(rows)


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
            backdrop-filter: blur(10px);
            transition: transform 120ms ease, box-shadow 120ms ease;
        }
        div.stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 16px 36px rgba(15, 23, 42, 0.12);
        }
        .stExpander {
            background: rgba(255, 255, 255, 0.76);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 14px;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(10px);
        }
        .block-container {
            position: relative;
            z-index: 1;
        }
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.65);
            border-radius: 12px;
            padding: 0.4rem 0.6rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def main():
    st.set_page_config(page_title="BHH Enrollment Command Center", layout="wide")
    apply_global_styles()

    st.markdown('<div class="cc-header">BHH Enrollment Command Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="cc-subtle">Live Notion view with enrollment progress and hygiene signals.</div>', unsafe_allow_html=True)

    pages = load_pages()
    df = pages_to_df(pages)

    if "selected_status" not in st.session_state:
        st.session_state.selected_status = "All"
    if "selected_source" not in st.session_state:
        st.session_state.selected_source = "All"

    source_options = ["All"] + [label for label, _ in config.DATABASES]
    st.markdown("")
    st.selectbox("Source", source_options, key="selected_source")

    base_df = df.copy()
    if st.session_state.selected_source != "All":
        base_df = base_df[base_df["Source"] == st.session_state.selected_source]

    total_count = len(base_df)
    missing_assigned = (base_df["Assigned Staff"] == "(unassigned)").sum()
    missing_next_step = (base_df["Next Step"] == "").sum()
    stale_count = base_df["_is_stale"].sum()

    current_enrolled = base_df["Status"].isin(ENROLLED_STATUSES).sum()
    percent_complete = 0 if ENROLLMENT_GOAL == 0 else current_enrolled / ENROLLMENT_GOAL
    remaining = max(ENROLLMENT_GOAL - current_enrolled, 0)

    st.markdown("")
    goal_cols = st.columns([2, 3])
    with goal_cols[0]:
        st.markdown(
            f"""
            <div class="goal-card">
                <div class="goal-label">Current Enrolled</div>
                <div class="goal-value">{current_enrolled}</div>
                <div class="goal-label">Goal: {ENROLLMENT_GOAL} • Remaining: {remaining}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with goal_cols[1]:
        st.markdown('<div class="goal-label">Progress to Goal</div>', unsafe_allow_html=True)
        st.progress(min(max(percent_complete, 0.0), 1.0))
        st.markdown(
            f'<div class="goal-label">{percent_complete:.0%} complete</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    build_kpi_cards(
        [
            {"label": "Total Applications", "value": total_count},
            {"label": f"Missing {config.PROP_ASSIGNED}", "value": missing_assigned},
            {"label": f"Missing {config.PROP_NEXT_STEP}", "value": missing_next_step},
            {"label": f"Stale >= {config.STALE_DAYS} days", "value": stale_count},
        ]
    )

    st.subheader(f"{config.PROP_STAGE} Overview")
    status_counts = base_df["Status"].value_counts().items()
    build_status_cards(list(status_counts), total_count)

    st.caption(f"Selected {config.PROP_STAGE}: {st.session_state.selected_status}")

    filter_cols = st.columns(3)
    stale_only = filter_cols[0].checkbox("Stale only", value=False)
    unassigned_only = filter_cols[1].checkbox("Unassigned only", value=False)
    missing_next_step_only = filter_cols[2].checkbox("Missing Next Step only", value=False)

    filtered = base_df.copy()
    if st.session_state.selected_status != "All":
        filtered = filtered[filtered["Status"] == st.session_state.selected_status]
    if stale_only:
        filtered = filtered[filtered["_is_stale"]]
    if unassigned_only:
        filtered = filtered[filtered["Assigned Staff"] == "(unassigned)"]
    if missing_next_step_only:
        filtered = filtered[filtered["Next Step"] == ""]

    table_cols = [
        "Name",
        "Source",
        "Status",
        "Assigned Staff",
        "Next Step",
        "Days Since Edit",
        "Last Edited",
        "Notion URL",
    ]
    display_df = filtered[table_cols + ["_files"]].sort_values(
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
        },
    )

    st.markdown("")
    st.subheader("Student Drill-Down")
    for _, row in display_df.iterrows():
        title = f"{row['Name']} — {row['Status']}"
        with st.expander(title, expanded=False):
            st.markdown(f"**Assigned Staff:** {row['Assigned Staff']}")
            st.markdown(f"**Last Edited:** {row['Last Edited']}")
            st.markdown("**Notion Page:**")
            st.link_button("Open in Notion", row["Notion URL"])

            files = row["_files"]
            if files:
                st.markdown("**Documents:**")
                for f in files:
                    st.markdown(f"- [{f['name']}]({f['url']})")
            else:
                st.markdown("**Documents:** None found")


if __name__ == "__main__":
    main()
