"""
Reusable Streamlit components for assessment rubric.
Extracted from staff_survey.py for use in dashboard and other interfaces.
"""
import json
from statistics import mean
import streamlit as st


def scale_input(label: str, key: str, help_text: str = "", initial_value=None):
    """
    Radio input for 1-5 scale assessment.
    Returns 1-5 integer or None when not selected.
    """
    options = ["— (not selected)", 5, 4, 3, 2, 1]
    default_index = 0
    
    # If we have a saved value, find its index
    if initial_value and initial_value in options:
        default_index = options.index(initial_value)
    
    val = st.radio(label, options, index=default_index, key=key, help=help_text, horizontal=True)
    return None if val == "— (not selected)" else int(val)


def avg_or_none(values):
    """Calculate average of numeric values or return None."""
    nums = [v for v in values if isinstance(v, int)]
    return round(mean(nums), 1) if nums else None


def render_applicant_snapshot(key_prefix: str = "", initial_data: dict = None):
    """
    Render the applicant snapshot section.
    Returns dict with student info.
    """
    if initial_data is None:
        initial_data = {}
    
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("Applicant Snapshot")
        student_name = st.text_input(
            "Student Name",
            value=initial_data.get("student_name", ""),
            key=f"{key_prefix}_student_name"
        )
        applying_grade = st.number_input(
            "Applying for Grade",
            min_value=6,
            max_value=12,
            step=1,
            value=int(initial_data.get("applying_grade", 9)),
            key=f"{key_prefix}_applying_grade"
        )
    
    with col_right:
        st.subheader("Intake Details")
        school_year = st.text_input(
            "School Year",
            value=initial_data.get("school_year", ""),
            key=f"{key_prefix}_school_year"
        )
        division = st.radio(
            "Division / Track",
            ["Boys Division", "Neiros Division", "Legacy Division"],
            index=["Boys Division", "Neiros Division", "Legacy Division"].index(
                initial_data.get("division", "Neiros Division")
            ),
            key=f"{key_prefix}_division",
            horizontal=True,
        )
        primary_contact_source = st.selectbox(
            "Primary Contact Source",
            ["", "Local", "Shliach", "Referral", "OOT", "Other"],
            index=["", "Local", "Shliach", "Referral", "OOT", "Other"].index(
                initial_data.get("primary_contact_source", "")
            ),
            key=f"{key_prefix}_primary_contact_source",
        )
        date_first_contact = st.date_input(
            "Date of First Contact",
            value=initial_data.get("date_first_contact"),
            key=f"{key_prefix}_date_first_contact"
        )
        assigned_staff_lead = st.text_input(
            "Assigned Staff Lead",
            value=initial_data.get("assigned_staff_lead", ""),
            key=f"{key_prefix}_assigned_staff_lead"
        )
    
    return {
        "student_name": student_name,
        "applying_grade": applying_grade,
        "school_year": school_year,
        "division": division,
        "primary_contact_source": primary_contact_source,
        "date_first_contact": str(date_first_contact) if date_first_contact else "",
        "assigned_staff_lead": assigned_staff_lead,
    }


def render_neiros_rubric(key_prefix: str = "", initial_data: dict = None):
    """
    Render Neiros Division rubric (5 criteria).
    Returns list of scores and dict of notes.
    """
    if initial_data is None:
        initial_data = {}
    
    scores = {}
    notes = {}
    
    st.markdown("### Neiros Division (Chassidish Girls)")
    
    c1, c2 = st.columns(2)
    
    with c1:
        scores["hashkafah"] = scale_input(
            "Hashkafah",
            f"{key_prefix}_neiros_hashkafah",
            initial_value=initial_data.get("scores", {}).get("neiros", {}).get("hashkafah")
        )
        notes["hashkafah"] = st.text_area(
            "Hashkafah Notes",
            value=initial_data.get("scores", {}).get("neiros", {}).get("notes", {}).get("hashkafah", ""),
            key=f"{key_prefix}_neiros_hashkafah_notes"
        )
        
        scores["social_functioning"] = scale_input(
            "Social Functioning",
            f"{key_prefix}_neiros_social",
            initial_value=initial_data.get("scores", {}).get("neiros", {}).get("social_functioning")
        )
        notes["social_functioning"] = st.text_area(
            "Social Functioning Notes",
            value=initial_data.get("scores", {}).get("neiros", {}).get("notes", {}).get("social_functioning", ""),
            key=f"{key_prefix}_neiros_social_notes"
        )
        
        scores["emotional_stability"] = scale_input(
            "Emotional Stability",
            f"{key_prefix}_neiros_emotional",
            initial_value=initial_data.get("scores", {}).get("neiros", {}).get("emotional_stability")
        )
        notes["emotional_stability"] = st.text_area(
            "Emotional Stability Notes",
            value=initial_data.get("scores", {}).get("neiros", {}).get("notes", {}).get("emotional_stability", ""),
            key=f"{key_prefix}_neiros_emotional_notes"
        )
    
    with c2:
        scores["academic_readiness"] = scale_input(
            "Academic Readiness",
            f"{key_prefix}_neiros_academic",
            initial_value=initial_data.get("scores", {}).get("neiros", {}).get("academic_readiness")
        )
        notes["academic_readiness"] = st.text_area(
            "Academic Readiness Notes",
            value=initial_data.get("scores", {}).get("neiros", {}).get("notes", {}).get("academic_readiness", ""),
            key=f"{key_prefix}_neiros_academic_notes"
        )
        
        scores["financial_participation"] = scale_input(
            "Financial Participation",
            f"{key_prefix}_neiros_financial",
            initial_value=initial_data.get("scores", {}).get("neiros", {}).get("financial_participation")
        )
        notes["financial_participation"] = st.text_area(
            "Financial Participation Notes",
            value=initial_data.get("scores", {}).get("neiros", {}).get("notes", {}).get("financial_participation", ""),
            key=f"{key_prefix}_neiros_financial_notes"
        )
    
    return {
        "scores": scores,
        "notes": notes,
        "score_list": [scores.get(k) for k in ["hashkafah", "social_functioning", "emotional_stability", "academic_readiness", "financial_participation"]]
    }


def render_legacy_rubric(key_prefix: str = "", initial_data: dict = None):
    """
    Render Legacy Division rubric (6 criteria).
    Returns list of scores and dict of notes.
    """
    if initial_data is None:
        initial_data = {}
    
    scores = {}
    notes = {}
    
    st.markdown("### Legacy Division (Boys & Girls – General Track)")
    
    c1, c2 = st.columns(2)
    
    with c1:
        scores["jewish_growth_orientation"] = scale_input(
            "Jewish Growth Orientation",
            f"{key_prefix}_legacy_jewish_growth",
            initial_value=initial_data.get("scores", {}).get("legacy", {}).get("jewish_growth_orientation")
        )
        notes["jewish_growth_orientation"] = st.text_area(
            "Jewish Growth Orientation Notes",
            value=initial_data.get("scores", {}).get("legacy", {}).get("notes", {}).get("jewish_growth_orientation", ""),
            key=f"{key_prefix}_legacy_jewish_growth_notes"
        )
        
        scores["emotional_stability"] = scale_input(
            "Emotional Stability",
            f"{key_prefix}_legacy_emotional",
            initial_value=initial_data.get("scores", {}).get("legacy", {}).get("emotional_stability")
        )
        notes["emotional_stability"] = st.text_area(
            "Emotional Stability Notes",
            value=initial_data.get("scores", {}).get("legacy", {}).get("notes", {}).get("emotional_stability", ""),
            key=f"{key_prefix}_legacy_emotional_notes"
        )
        
        scores["social_integration"] = scale_input(
            "Social Integration",
            f"{key_prefix}_legacy_social",
            initial_value=initial_data.get("scores", {}).get("legacy", {}).get("social_integration")
        )
        notes["social_integration"] = st.text_area(
            "Social Integration Notes",
            value=initial_data.get("scores", {}).get("legacy", {}).get("notes", {}).get("social_integration", ""),
            key=f"{key_prefix}_legacy_social_notes"
        )
    
    with c2:
        scores["academic_readiness"] = scale_input(
            "Academic Readiness",
            f"{key_prefix}_legacy_academic",
            initial_value=initial_data.get("scores", {}).get("legacy", {}).get("academic_readiness")
        )
        notes["academic_readiness"] = st.text_area(
            "Academic Readiness Notes",
            value=initial_data.get("scores", {}).get("legacy", {}).get("notes", {}).get("academic_readiness", ""),
            key=f"{key_prefix}_legacy_academic_notes"
        )
        
        scores["behavior_structure_acceptance"] = scale_input(
            "Behavior / Structure Acceptance",
            f"{key_prefix}_legacy_behavior",
            initial_value=initial_data.get("scores", {}).get("legacy", {}).get("behavior_structure_acceptance")
        )
        notes["behavior_structure_acceptance"] = st.text_area(
            "Behavior / Structure Acceptance Notes",
            value=initial_data.get("scores", {}).get("legacy", {}).get("notes", {}).get("behavior_structure_acceptance", ""),
            key=f"{key_prefix}_legacy_behavior_notes"
        )
        
        scores["financial_participation"] = scale_input(
            "Financial Participation",
            f"{key_prefix}_legacy_financial",
            initial_value=initial_data.get("scores", {}).get("legacy", {}).get("financial_participation")
        )
        notes["financial_participation"] = st.text_area(
            "Financial Participation Notes",
            value=initial_data.get("scores", {}).get("legacy", {}).get("notes", {}).get("financial_participation", ""),
            key=f"{key_prefix}_legacy_financial_notes"
        )
    
    return {
        "scores": scores,
        "notes": notes,
        "score_list": [scores.get(k) for k in ["jewish_growth_orientation", "emotional_stability", "social_integration", "academic_readiness", "behavior_structure_acceptance", "financial_participation"]]
    }


def render_disqualifiers(key_prefix: str = "", initial_data: dict = None):
    """
    Render automatic disqualifiers section.
    Returns dict with disqualifier status.
    """
    if initial_data is None:
        initial_data = {}
    
    st.subheader("Automatic Disqualifiers")
    st.write("If **any** box is checked → Overall Rating = **0 (Disqualified)**")
    
    disqualifiers = initial_data.get("automatic_disqualifiers", {})
    
    dq1 = st.checkbox(
        "Halachic Jewish status unresolved",
        value=disqualifiers.get("halachic_status_unresolved", False),
        key=f"{key_prefix}_dq_halachic"
    )
    dq2 = st.checkbox(
        "Issues beyond BHH's capacity",
        value=disqualifiers.get("beyond_capacity", False),
        key=f"{key_prefix}_dq_capacity"
    )
    dq3 = st.checkbox(
        "Family unwilling to cooperate with guidance or finances",
        value=disqualifiers.get("family_unwilling", False),
        key=f"{key_prefix}_dq_family"
    )
    dq4 = st.checkbox(
        "Open opposition to BHH values or expectations",
        value=disqualifiers.get("opposition_to_values", False),
        key=f"{key_prefix}_dq_values"
    )
    
    return {
        "halachic_status_unresolved": dq1,
        "beyond_capacity": dq2,
        "family_unwilling": dq3,
        "opposition_to_values": dq4,
        "disqualified": any([dq1, dq2, dq3, dq4]),
    }


def render_overall_rating(avg_score, disqualified, key_prefix: str = "", initial_data: dict = None):
    """
    Render overall rating and summary section.
    Returns overall_rating and summary_comments.
    """
    if initial_data is None:
        initial_data = {}
    
    st.subheader("Overall Rating Summary")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Average Score", "—" if avg_score is None else f"{avg_score}")
    
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
                key=f"{key_prefix}_overall_rating_locked",
            )
        else:
            initial_rating = initial_data.get("overall_rating", 0)
            rating_index = [opt[0] for opt in rating_options].index(initial_rating) if initial_rating in [opt[0] for opt in rating_options] else 0
            overall_rating = st.selectbox(
                "Overall Rating",
                options=[opt[0] for opt in rating_options],
                format_func=lambda v: dict(rating_options)[v],
                index=rating_index,
                key=f"{key_prefix}_overall_rating",
            )
    
    summary_comments = st.text_area(
        "Summary Comments (optional, concise)",
        value=initial_data.get("summary_comments", ""),
        key=f"{key_prefix}_summary_comments"
    )
    
    return {
        "overall_rating": overall_rating,
        "summary_comments": summary_comments,
    }


def render_next_actions(key_prefix: str = "", initial_data: dict = None):
    """
    Render next actions section.
    Returns dict with next actions details.
    """
    if initial_data is None:
        initial_data = {}
    
    st.subheader("Required Next Action")
    
    action_options = [
        "Schedule follow-up conversation",
        "Request additional records / references",
        "Invite for visit or shadow day",
        "Pause and reassess",
        "Close file",
    ]
    
    next_actions = st.multiselect(
        "Next Action(s)",
        action_options,
        default=initial_data.get("next_actions", []),
        key=f"{key_prefix}_next_actions",
    )
    
    action_owner = st.text_input(
        "Action Owner",
        value=initial_data.get("action_owner", ""),
        key=f"{key_prefix}_action_owner"
    )
    
    target_date = st.date_input(
        "Target Date",
        value=initial_data.get("target_date"),
        key=f"{key_prefix}_target_date"
    )
    
    return {
        "next_actions": next_actions,
        "action_owner": action_owner,
        "target_date": str(target_date) if target_date else "",
    }


def build_assessment_payload(applicant_data: dict, rubric_data: dict, disqualifiers: dict, rating_data: dict, actions_data: dict) -> dict:
    """
    Build complete assessment payload from all sections.
    """
    division = applicant_data.get("division", "Boys Division")
    
    if division == "Neiros Division":
        scores = rubric_data.get("scores", {})
        notes_dict = rubric_data.get("notes", {})
    elif division == "Legacy Division":
        scores = rubric_data.get("scores", {})
        notes_dict = rubric_data.get("notes", {})
    else:
        scores = {}
        notes_dict = {}
    
    avg_score = avg_or_none(rubric_data.get("score_list", []))
    
    payload = {
        "student_name": applicant_data.get("student_name"),
        "applying_grade": applicant_data.get("applying_grade"),
        "school_year": applicant_data.get("school_year"),
        "division": division,
        "primary_contact_source": applicant_data.get("primary_contact_source"),
        "date_first_contact": applicant_data.get("date_first_contact"),
        "assigned_staff_lead": applicant_data.get("assigned_staff_lead"),
        "scores": {
            "neiros": scores if division == "Neiros Division" else {},
            "legacy": scores if division == "Legacy Division" else {},
            "notes": notes_dict,
        },
        "automatic_disqualifiers": disqualifiers,
        "disqualified": disqualifiers.get("disqualified", False),
        "average_score": avg_score,
        "overall_rating": rating_data.get("overall_rating", 0),
        "summary_comments": rating_data.get("summary_comments", ""),
        "next_actions": actions_data.get("next_actions", []),
        "action_owner": actions_data.get("action_owner", ""),
        "target_date": actions_data.get("target_date", ""),
        "assessment_timestamp": datetime.now().isoformat(),
    }
    
    return payload


from datetime import datetime
