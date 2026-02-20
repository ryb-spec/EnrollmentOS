DATABASE_ID = "2c6bba394fae802cb4dbc8db3ddc1ea6"

DATABASES = [
    ("New Prospects", "2c6bba394fae802cb4dbc8db3ddc1ea6"),
    ("Reenrollment", "2c6bba394fae80d392bedbb0c3df36e1"),
]

# Your canonical application stage field
PROP_STAGE = "Status"

# Other key fields
PROP_ASSIGNED = "Assigned Staff"
PROP_NEXT_STEP = "Next Step"

STALE_DAYS = 14
EXCLUDE_STALE_STAGES = {"Not a Good Fit"}

SUMMARY_CSV = "enrollment_health_summary.csv"
ACTIONS_CSV = "enrollment_health_action_list.csv"
