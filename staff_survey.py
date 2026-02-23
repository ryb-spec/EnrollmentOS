import json
from statistics import mean

import streamlit as st


st.set_page_config(page_title="BHH Applicant Assessment", layout="wide")

st.title("Bader Hillel High – Applicant Assessment")
st.caption("Recruitment prioritization tool only. Final admissions decisions remain with BHH principals.")


def scale_input(label: str, key: str, help_text: str = ""):
    """Return 1-5 integer or None when not selected."""
    options = ["— (not selected)", 5, 4, 3, 2, 1]
    val = st.radio(label, options, index=0, key=key, help=help_text, horizontal=True)
    return None if val == "— (not selected)" else int(val)


def avg_or_none(values):
    nums = [v for v in values if isinstance(v, int)]
    return round(mean(nums), 1) if nums else None


col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Applicant Snapshot")
    student_name = st.text_input("Student Name", key="student_name")
    applying_grade = st.number_input("Applying for Grade", min_value=6, max_value=12, step=1, key="applying_grade")

with col_right:
    st.subheader("Intake Details")
    school_year = st.text_input("School Year", key="school_year")
    division = st.radio(
        "Division / Track",
        ["Boys Division", "Neiros Division", "Legacy Division"],
        key="division",
        horizontal=True,
    )
    primary_contact_source = st.selectbox(
        "Primary Contact Source",
        ["", "Local", "Shliach", "Referral", "OOT", "Other"],
        key="primary_contact_source",
    )
    date_first_contact = st.date_input("Date of First Contact", key="date_first_contact")
    assigned_staff_lead = st.text_input("Assigned Staff Lead", key="assigned_staff_lead")

st.divider()

st.subheader("Core Fit Assessment (1–5 Scale)")
st.write("Check **one** per category. Add brief evidence notes only where needed.")

neiros_scores = []
legacy_scores = []

if division == "Neiros Division":
    st.markdown("### A. Neiros Division (Chassidish Girls)")

    c1, c2 = st.columns(2)
    with c1:
        neiros_hashkafah = scale_input("Hashkafah", "neiros_hashkafah")
        st.text_area("Hashkafah Notes", key="neiros_hashkafah_notes")

        neiros_social = scale_input("Social Functioning", "neiros_social")
        st.text_area("Social Functioning Notes", key="neiros_social_notes")

        neiros_emotional = scale_input("Emotional Stability", "neiros_emotional")
        st.text_area("Emotional Stability Notes", key="neiros_emotional_notes")

    with c2:
        neiros_academic = scale_input("Academic Readiness", "neiros_academic")
        st.text_area("Academic Readiness Notes", key="neiros_academic_notes")

        neiros_financial = scale_input("Financial Participation", "neiros_financial")
        st.text_area("Financial Participation Notes", key="neiros_financial_notes")

    neiros_scores = [
        neiros_hashkafah,
        neiros_social,
        neiros_emotional,
        neiros_academic,
        neiros_financial,
    ]

elif division == "Legacy Division":
    st.markdown("### B. Legacy Division (Boys & Girls – General Track)")
    st.write("(Complete this section only if applicable)")

    c1, c2 = st.columns(2)
    with c1:
        legacy_jewish_growth = scale_input("Jewish Growth Orientation", "legacy_jewish_growth")
        st.text_area("Jewish Growth Orientation Notes", key="legacy_jewish_growth_notes")

        legacy_emotional = scale_input("Emotional Stability", "legacy_emotional")
        st.text_area("Emotional Stability Notes", key="legacy_emotional_notes")

        legacy_social = scale_input("Social Integration", "legacy_social")
        st.text_area("Social Integration Notes", key="legacy_social_notes")

    with c2:
        legacy_academic = scale_input("Academic Readiness", "legacy_academic")
        st.text_area("Academic Readiness Notes", key="legacy_academic_notes")

        legacy_behavior = scale_input("Behavior / Structure Acceptance", "legacy_behavior")
        st.text_area("Behavior / Structure Acceptance Notes", key="legacy_behavior_notes")

        legacy_financial = scale_input("Financial Participation", "legacy_financial")
        st.text_area("Financial Participation Notes", key="legacy_financial_notes")

    legacy_scores = [
        legacy_jewish_growth,
        legacy_emotional,
        legacy_social,
        legacy_academic,
        legacy_behavior,
        legacy_financial,
    ]

else:
    st.info("Boys Division selected. (A dedicated Boys scoring section can be added if needed.)")

st.divider()

st.subheader("Automatic Disqualifiers")
st.write("If **any** box is checked → Overall Rating = **0 (Disqualified)**")

dq1 = st.checkbox("Halachic Jewish status unresolved", key="dq_halachic")
dq2 = st.checkbox("Issues beyond BHH’s capacity", key="dq_capacity")
dq3 = st.checkbox("Family unwilling to cooperate with guidance or finances", key="dq_family")
dq4 = st.checkbox("Open opposition to BHH values or expectations", key="dq_values")

disqualified = any([dq1, dq2, dq3, dq4])

st.divider()

st.subheader("Overall Rating Summary")

visible_scores = neiros_scores if division == "Neiros Division" else legacy_scores if division == "Legacy Division" else []
avg_score = avg_or_none(visible_scores)

c1, c2 = st.columns([1, 2])
with c1:
    st.metric("Average Score (if applicable)", "—" if avg_score is None else f"{avg_score}")

with c2:
    rating_options = [
        (5, "A-Rated (Excellent fit; prioritize)"),
        (4, "Strong Fit (Active follow-up)"),
        (3, "Possible Fit (Evaluate further)"),
        (2, "Marginal Fit (Proceed cautiously)"),
        (1, "Poor Fit (Do not advance)"),
        (0, "Disqualified"),
    ]

    if disqualified:
        st.error("Disqualifier checked → Overall Rating forced to 0 (Disqualified).")
        overall_rating = 0
        st.selectbox(
            "Overall Rating",
            options=[opt[0] for opt in rating_options],
            format_func=lambda v: dict(rating_options)[v],
            index=[opt[0] for opt in rating_options].index(0),
            disabled=True,
            key="overall_rating_locked",
        )
    else:
        overall_rating = st.selectbox(
            "Overall Rating",
            options=[opt[0] for opt in rating_options],
            format_func=lambda v: dict(rating_options)[v],
            index=0,
            key="overall_rating",
        )

summary_comments = st.text_area("Summary Comments (optional, concise)", key="summary_comments")

st.divider()

st.subheader("Required Next Action")
next_actions = st.multiselect(
    "Next Action(s)",
    [
        "Schedule follow-up conversation",
        "Request additional records / references",
        "Invite for visit or shadow day",
        "Pause and reassess",
        "Close file",
    ],
    key="next_actions",
)
action_owner = st.text_input("Action Owner", key="action_owner")
target_date = st.date_input("Target Date", key="target_date")

st.divider()

st.subheader("Preview Output (JSON)")
payload = {
    "student_name": student_name,
    "applying_grade": applying_grade,
    "school_year": school_year,
    "division": division,
    "primary_contact_source": primary_contact_source,
    "date_first_contact": str(date_first_contact),
    "assigned_staff_lead": assigned_staff_lead,
    "scores": {
        "neiros": {
            "hashkafah": st.session_state.get("neiros_hashkafah"),
            "social_functioning": st.session_state.get("neiros_social"),
            "emotional_stability": st.session_state.get("neiros_emotional"),
            "academic_readiness": st.session_state.get("neiros_academic"),
            "financial_participation": st.session_state.get("neiros_financial"),
            "notes": {
                "hashkafah": st.session_state.get("neiros_hashkafah_notes"),
                "social_functioning": st.session_state.get("neiros_social_notes"),
                "emotional_stability": st.session_state.get("neiros_emotional_notes"),
                "academic_readiness": st.session_state.get("neiros_academic_notes"),
                "financial_participation": st.session_state.get("neiros_financial_notes"),
            },
        },
        "legacy": {
            "jewish_growth_orientation": st.session_state.get("legacy_jewish_growth"),
            "emotional_stability": st.session_state.get("legacy_emotional"),
            "social_integration": st.session_state.get("legacy_social"),
            "academic_readiness": st.session_state.get("legacy_academic"),
            "behavior_structure_acceptance": st.session_state.get("legacy_behavior"),
            "financial_participation": st.session_state.get("legacy_financial"),
            "notes": {
                "jewish_growth_orientation": st.session_state.get("legacy_jewish_growth_notes"),
                "emotional_stability": st.session_state.get("legacy_emotional_notes"),
                "social_integration": st.session_state.get("legacy_social_notes"),
                "academic_readiness": st.session_state.get("legacy_academic_notes"),
                "behavior_structure_acceptance": st.session_state.get("legacy_behavior_notes"),
                "financial_participation": st.session_state.get("legacy_financial_notes"),
            },
        },
    },
    "automatic_disqualifiers": {
        "halachic_status_unresolved": dq1,
        "beyond_capacity": dq2,
        "family_unwilling": dq3,
        "opposition_to_values": dq4,
    },
    "disqualified": disqualified,
    "average_score": avg_score,
    "overall_rating": 0 if disqualified else overall_rating,
    "summary_comments": summary_comments,
    "next_actions": next_actions,
    "action_owner": action_owner,
    "target_date": str(target_date),
}

st.json(payload)
st.download_button(
    "Download assessment JSON",
    data=json.dumps(payload, indent=2),
    file_name=f"bhh_assessment_{(student_name or 'student').replace(' ', '_').lower()}.json",
    mime="application/json",
)
