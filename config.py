DATABASE_ID = "2c6bba394fae802cb4dbc8db3ddc1ea6"

DATABASES = [
    ("New Prospects", "2c6bba394fae802cb4dbc8db3ddc1ea6"),
    ("Reenrollment", "2c6bba394fae80d392bedbb0c3df36e1"),
]

REENROLLMENT_SOURCE_LABEL = "Reenrollment"

# Your canonical application stage field
PROP_STAGE = "Status"

# Other key fields
PROP_ASSIGNED = "Assigned Staff"
PROP_NEXT_STEP = "Next Step"

STALE_DAYS = 14
EXCLUDE_STALE_STAGES = {"Not a Good Fit"}

ENROLLED_STATUSES = {"Enrolled", "Accepted", "Active", "Reenrollment - Accepted"}

# Normalize source-specific statuses into a shared reporting vocabulary.
STATUS_NORMALIZATION = {
    "New Prospects": {
        "Application sent to fill out": "Prospect - Application Started",
        "Working on gathering references": "Prospect - In Review",
        "References sent to principals": "Prospect - In Review",
        "Application on pause": "Prospect - On Hold",
        "No Longer Interested": "Prospect - Closed",
        "Potential Visit": "Prospect - In Review",
        "Visit approved": "Prospect - Accepted",
        "Intake Sent": "Prospect - Accepted",
        "Not Contacted yet": "Prospect - New",
        "tried to contact": "Prospect - Outreach",
    },
    "Reenrollment": {
        "Reenrollment - Begin": "Reenrollment - Begin",
        "Reenrollment - Application Complete": "Reenrollment - Application Complete",
        "Reenrollment - Accepted": "Reenrollment - Accepted",
    },
}

STATUS_DEFAULTS_BY_SOURCE = {
    "New Prospects": "Prospect - New",
    REENROLLMENT_SOURCE_LABEL: "Reenrollment - Begin",
}



# Optional Google Form export integration (3 forms per student)
# Put CSV exports in the repo root (or adjust paths/headers below).
GOOGLE_FORM_TIMESTAMP_COLUMN = "Timestamp"
GOOGLE_FORM_EMAIL_COLUMN = "Email Address"
GOOGLE_FORM_NAME_COLUMN = "Student Name"

GOOGLE_FORM_FILES = {
    "parent": "google_form_parent_submission.csv",
    "reference_1": "google_form_reference_1.csv",
    "reference_2": "google_form_reference_2.csv",
}

# Optional: pull each form directly from Google Sheets in near real-time.
# Preferred format is full spreadsheet URL per form key.
GOOGLE_FORM_SPREADSHEET_URLS = {
    "parent": "https://docs.google.com/spreadsheets/d/13Ds8rrAwnPj2TMEF9CYYLsywGmFFCoFrMJcDnLTfG9A/edit?usp=sharing",
    "reference_1": "https://docs.google.com/spreadsheets/d/1LLmsZJLahf0BIxP2joqVFOd-zYCM_Bgx57EgbgrkI94/edit?usp=sharing",
    "reference_2": "https://docs.google.com/spreadsheets/d/15TAmXl0v4dGdzrVSJ7Ol0h5slmemF0ObtKayGQ7Zolw/edit?usp=sharing",
}

# Optional tab-name overrides for each form spreadsheet.
# Leave blank to use the sheet's default/first tab export.
GOOGLE_FORM_SHEETS = {
    "parent": "",
    "reference_1": "",
    "reference_2": "",
}

# Backward-compatible single-sheet setting (used only when
# GOOGLE_FORM_SPREADSHEET_URLS is not configured for a form key).
GOOGLE_FORMS_SPREADSHEET_ID = ""

# Notion properties used to match a student to form responses.
PROP_STUDENT_EMAIL = "Email"
PROP_STUDENT_ALT_EMAIL = "Parent Email"

# Packet scoring weights for form completeness (not staff rubric).
RUBRIC_WEIGHTS = {
    "parent": 50,
    "reference_1": 25,
    "reference_2": 25,
}

# Optional Notion fields for BHH staff rubric entry after all 3 forms are in.
# Set these to your exact property names in Notion.
PROP_STAFF_RUBRIC_SCORE = "BHH Rubric Score"
PROP_STAFF_RUBRIC_STATUS = "BHH Rubric Status"

SUMMARY_CSV = "enrollment_health_summary.csv"
ACTIONS_CSV = "enrollment_health_action_list.csv"
