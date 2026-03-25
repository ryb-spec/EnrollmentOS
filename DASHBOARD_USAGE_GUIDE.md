# Simplified Enrollment Dashboard - User Guide

## Quick Start

### Launch the Dashboard
```bash
streamlit run dashboard.py
```

---

## What You See

### 📊 Title & Purpose
**"Enrollment Action Dashboard"**
*Focus: Follow-up today + Stuck/Overdue students*

This is a daily action tool, not a reporting dashboard. It tells you exactly who to contact and who's delayed.

---

## Main Views

### 1️⃣ New Prospects (Default Tab)

#### 📈 Key Metrics (Top Row)
Four simple KPIs:
- **Total Active**: All students in pipeline (excluding "Not a Good Fit")
- **Follow-Up Today**: Students needing action NOW
- **Stuck / Overdue**: Students with delays (flagged automatically)
- **Enrolled**: Students who completed (Stage 5)

Each shows a count and percentage. Use these to understand your pipeline health at a glance.

#### 📋 Three View Options
Choose one action at a time:

**📞 Follow-Up Today**
- Shows only students who need follow-up
- Sorted by longest waiting first
- Next Step tells you what action to take
- Days Since Activity shows how long it's been

**⚠️ Stuck / Overdue**
- Shows only students with delays
- Flag Type tells you why:
  - **🔴 OVERDUE**: Exceeded stage time limit
  - **⚠️ STUCK**: No movement for 7+ days
- Days In Stage shows actual delay count

**📋 All Active**
- Complete list of all active students
- Sorted by activity (newest first)
- Use for daily status check

#### 📊 Columns in Table
- **Name**: Student name (clickable in future)
- **Pipeline Stage**: Where they are in process
- **Assigned Staff**: Who owns this student
- **Next Step**: What action is recommended
- **Days Since Activity**: How long since last update

---

### 2️⃣ Reenrollment Tab

#### Shows Reenrollment Records Only
Separate pipeline for students continuing next year.

#### Reenrollment Status
Auto-classified into 4 buckets:
- **Confirmed**: Returning for sure (95% weight)
- **In Progress**: Working through enrollment (95% weight)
- **At Risk**: Might not return (50% weight)
- **Not Returning**: Confirmed no (0% weight)

#### Projected Returning KPI
Shows weighted projection:
- Example: 80 confirmed + 10 in progress = ~85 projected

---

## Understanding Flags

### Who Gets "Follow-Up Today"?
Students with BOTH:
1. **Next Step is filled in** (not empty)
2. **Not contacted for 2+ days** (or not edited for 2+ days)

This shows students you planned to talk to but haven't reached out in a while.

### Who Gets "OVERDUE"?
Different rules by stage:
- **Stage 2 (Principal Review)**: > 14 days = Overdue
- **Stage 3 (Application)**: > 10 days = Overdue
- **Stage 4 (Interview)**: > 7 days = Overdue

Example: If a Principal Review hasn't moved in 15 days → **OVERDUE**

### Who Gets "STUCK"?
Any student who hasn't been contacted/edited for 7+ days, even if not overdue.

---

## Daily Workflow

### Morning (5 min)
1. Open dashboard
2. Check Follow-Up Today count
3. Review the list
4. Call/email the students listed
5. Update "Last Contacted" in Notion

### During Day
1. Check Stuck/Overdue count
2. Prioritize any overdue (red flag)
3. Move them forward or mark as complete

### End of Day
1. Check All Active to spot new trends
2. Note any students who changed status

---

## How Data Updates

**⏱️ Automatic Refresh**: Every 5 minutes (cache duration)

**Manual Refresh**: Press **Ctrl+R** or **Cmd+R** in browser

**What Triggers Follow-Up**:
- Update "Last Contacted" field in Notion
- Or edit any student field (updates Last Edited auto)
- Field must be 24+ hours old to show follow-up

**What Triggers Stuck Flag**:
- Not updated for 7+ days in this stage
- Automatic - no manual action needed

---

## Data Requirements in Notion

### Required Fields (Must Exist)
- ✅ **Name** - Student name
- ✅ **Source** - "New Prospects" or "Reenrollment"
- ✅ **Status** - Maps to pipeline stage
- ✅ **Last Contacted** - Last communication date (optional but recommended)

### Important for New Prospects
- **Assigned Staff** - Who owns this student
- **Next Step** - Filled automatically based on stage

### Optional Fields
- Track, Target School Year, Gender, Grade, Notes
- (These are tracked but not shown in default view)

---

## Common Questions

### "Why isn't a student showing in Follow-Up Today?"
Possible reasons:
1. **Next Step is empty** - Add an action in Notion
2. **Too recent** - Last contacted less than 2 days ago
3. **Student is "Not a Good Fit"** - Auto-excluded

### "How do I add a student?"
Create a new record in Notion with:
- Name
- Status (mapped to pipeline stage)
- Source (New Prospects or Reenrollment)

### "Can I change the thresholds?"
Not in the UI (deliberate limitation). To change:
1. Edit `dashboard.py`
2. Modify `FOLLOW_UP_DAYS_THRESHOLD`, `STUCK_DAYS_THRESHOLD`, or `STAGE_OVERDUE_RULES`
3. Restart Streamlit

---

## Color Coding (Future)

Currently styled for easy reading. Future versions will add:
- 🔴 Red = Overdue (immediate action)
- 🟡 Yellow = Needs follow-up
- 🟢 Green = Active and moving

---

## Troubleshooting

### Dashboard won't load
```bash
# Check Python
python --version

# Check Streamlit
pip install streamlit

# Check Notion token
echo $env:NOTION_TOKEN  # Windows
```

### Wrong student counts
1. Check Notion records (exclude "Not a Good Fit")
2. Verify Status field is filled for each student
3. Check if Source is "New Prospects" vs "Reenrollment"

### Following up but student doesn't show
1. Ensure "Last Contacted" is today's date or very recent
2. Check if Next Step field is empty (must have action)

---

## Tips

### ✅ DO
- Review Follow-Up Today every morning
- Update Last Contacted after each call
- Use Pipeline Stage to determine next action
- Check Stuck/Overdue mid-week

### ❌ DON'T
- Try to forecast using this dashboard (use reports instead)
- Expect student profile details (view in Notion directly)
- Use for demographic analysis (not built for that)

---

## Summary

This dashboard answers ONE question: **What do I do TODAY?**

- **Follow-Up Today** = Call these students now
- **Stuck/Overdue** = These need urgent help

Everything else is noise. Keep it focused. Keep it fast.

---

**Questions?** Check REFACTORING_NOTES.md for technical details.
