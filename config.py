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

# Statuses that count as "enrolled prospects" in projection logic
ENROLLED_STATUSES = {"Enrolled", "Accepted", "Active", "Reenrollment - Accepted"}

# -----------------------------
# Status normalization
# -----------------------------
# Normalize source-specific statuses into a shared reporting vocabulary.
# Structure is:
#   STATUS_NORMALIZATION = {
#       "<Source Label>": { "<Raw Status>": "<Normalized Status>", ... },
#       ...
#   }
STATUS_NORMALIZATION = {
    "New Prospects": {
        # Prospects
        "Working on gathering references": "Prospect - In Review",
        "References sent to principals": "Prospect - In Review",
        "Potential Visit": "Prospect - In Review",
        "No Longer Interested": "Prospect - Closed",
        "Not Contacted yet": "Prospect - New",
        "New Prospects": "Prospect - New",
    },
    "Reenrollment": {
        # Reenrollment pipeline
        "Reenrollment - Begin": "Reenrollment - Begin",
        "Reenrollment - Application Complete": "Reenrollment - Application Complete",

        # Normalize "in progress" variants to one label used for KPIs
        "Reenrollment - In Progress": "Reenrollment In Progress",
        "Reenrollment In Progress": "Reenrollment In Progress",

        # Normalize retention risk variants to one label used for KPIs
        "Retention Risk": "Reenrollment Retention Risk",
        "Reenrollment - Retention Risk": "Reenrollment Retention Risk",
        "Reenrollment Retention Risk": "Reenrollment Retention Risk",

        "Reenrollment - Accepted": "Reenrollment - Accepted",
    },
}

# When a page has no Status set, default by Source
STATUS_DEFAULTS_BY_SOURCE = {
    "New Prospects": "Prospect - New",
    REENROLLMENT_SOURCE_LABEL: "Reenrollment - Begin",
}

# -----------------------------
# Projection logic inputs
# -----------------------------
REENROLLMENT_PROJECTION_RATE = 0.95

# These must match the *normalized* labels produced above
RETENTION_RISK_STATUSES = {"Reenrollment Retention Risk"}

REENROLLMENT_IN_PROGRESS_STATUSES = {
    "Reenrollment - Begin",
    "Reenrollment - Application Complete",
    "Reenrollment In Progress",
}

# Hide these statuses in dashboard cards while still counting records in data exports.
HIDE_STATUS_CARDS = {"Prospect - New", "Prospect - Closed"}

# Used to exclude closed prospects from "active totals"
CLOSED_PROSPECT_STATUSES = {"Prospect - Closed"}


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

# Assessment properties (for staff assessment modal)
# Add these properties to your Notion database if they don't exist
PROP_ASSESSMENT_STATUS = "Assessment Status"
PROP_ASSESSMENT_DATE = "Assessment Date"
PROP_ASSESSOR_NAME = "Assessor Name"
PROP_ASSESSMENT_GRADE = "Assessment Grade"
PROP_ASSESSOR_EMAIL = "Assessor Email"

# -------- EMAIL REMINDER CONFIGURATION --------
# Gmail SMTP setup (using app password for 2FA accounts)
EMAIL_SENDER = "ryb@hillelhigh.com"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
# Set GMAIL_APP_PASSWORD env var: setx GMAIL_APP_PASSWORD "your-16-char-password"
# Get app password: https://myaccount.google.com/apppasswords (requires 2FA enabled)

# Reminder settings
EMAIL_REMINDER_HOURS_BETWEEN = 48  # Remind every 2 business days (48 hours)
EMAIL_REMINDER_HOUR_OF_DAY = 9  # Send at 9am (24-hour format)
# Disable email reminders for now
EMAIL_ENABLED = False

# Tracking file for reminder timestamps (local storage)
REMINDER_TRACKING_FILE = "assessment_reminders.json"

SUMMARY_CSV = "enrollment_health_summary.csv"
ACTIONS_CSV = "enrollment_health_action_list.csv"

# Statuses that should trigger an assessment / in-review workflow.
# Include common variants and misspellings from Notion data.
ASSESSMENT_STATUSES = {
    "Prospect - In Review",
    "References sent to principals",
    "References sent to principal",
}

# Statuses where references are sent — trigger assessment even if other fields are empty
REFERENCE_STATUSES = {
    "References sent to principals",
    "References sent to principal",
}
