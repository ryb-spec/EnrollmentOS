"""
Email reminder module for pending assessments.
Sends reminders to assigned staff when assessments are pending after 48 hours.
"""
import os
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config
import notion_io
import extractors


def load_reminder_tracking():
    """Load last reminder timestamps from local JSON file."""
    if not os.path.exists(config.REMINDER_TRACKING_FILE):
        return {}
    
    try:
        with open(config.REMINDER_TRACKING_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Error loading reminder tracking: {e}")
        return {}


def save_reminder_tracking(tracking_data):
    """Save reminder timestamps to local JSON file."""
    try:
        with open(config.REMINDER_TRACKING_FILE, "w") as f:
            json.dump(tracking_data, f, indent=2)
    except Exception as e:
        print(f"⚠️  Error saving reminder tracking: {e}")


def get_pending_assessments(pages):
    """
    Identify prospects needing assessment reminders.
    
    Returns list of dicts with:
    - prospect_name
    - assessor_email
    - assessor_name
    - page_id
    - status
    - days_in_review
    """
    pending = []
    
    for page in pages:
        props = page.get("properties", {})
        name = extractors.get_title(props)
        
        # Check status: must be "In Review" or similar
        raw_status = extractors.get_stage_value(props, config.PROP_STAGE)
        status = extractors.normalize_status(raw_status, page.get("_source", "(unknown)"), config)
        
        # Only pages with assessment-trigger statuses should get reminders
        if status not in getattr(config, "ASSESSMENT_STATUSES", {"Prospect - In Review"}):
            continue

        # For reference-sent statuses we include the page even if assigned/forms/email are missing
        raw_status = extractors.get_stage_value(props, config.PROP_STAGE) or ''
        raw_status_lower = raw_status.lower()
        is_reference_status = (
            status in getattr(config, "REFERENCE_STATUSES", set())
            or ("reference" in raw_status_lower and "princip" in raw_status_lower)
        )

        # Must have assigned staff for non-reference statuses
        assessor_names = extractors.get_multiselect_names(props, config.PROP_ASSIGNED)
        if not assessor_names and not is_reference_status:
            continue

        # Get assessor email (might be missing for reference-only statuses)
        assessor_email = extractors.get_rich_text(props, config.PROP_ASSESSOR_EMAIL) or ''

        # Must have all forms submitted for non-reference statuses
        from google_forms import get_student_form_summary
        form_indexes = {}  # We're just checking, not scoring
        form_summary = get_student_form_summary(form_indexes, props, name, config)
        if not form_summary["all_forms_submitted"] and not is_reference_status:
            continue
        
        # Must NOT have completed assessment
        assessment_status = extractors.get_select_like_value(props, config.PROP_ASSESSMENT_STATUS)
        if assessment_status == "Completed":
            continue
        
        # Calculate days in review
        last_edited = page.get("last_edited_time", "")
        days_since_edit = extractors.days_since(last_edited) if last_edited else 0
        
        pending.append({
            "prospect_name": name,
            "assessor_email": assessor_email,
            "assessor_name": ", ".join(assessor_names) if assessor_names else "",
            "page_id": page.get("id", ""),
            "status": status,
            "days_in_review": days_since_edit,
            "is_reference_status": is_reference_status,
        })
    
    return pending


def should_send_reminder(prospect_page_id: str, tracking_data: dict) -> bool:
    """
    Check if reminder should be sent for this prospect.
    Rules:
    - If never reminded: send now
    - If reminded before: only if 48+ hours have passed
    """
    if prospect_page_id not in tracking_data:
        return True
    
    last_reminder = tracking_data[prospect_page_id]
    try:
        last_time = datetime.fromisoformat(last_reminder)
        hours_since = (datetime.now() - last_time).total_seconds() / 3600
        return hours_since >= config.EMAIL_REMINDER_HOURS_BETWEEN
    except Exception:
        return True


def send_email_reminder(prospect_name: str, assessor_email: str, assessor_name: str, days_in_review: int):
    """
    Send assessment reminder email via Gmail.
    
    Returns:
        Dict with {success: bool, message: str}
    """
    try:
        gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
        if not gmail_app_password:
            return {
                "success": False,
                "message": "GMAIL_APP_PASSWORD environment variable not set"
            }
        
        # Compose email
        subject = f"Assessment Reminder: {prospect_name}"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2>Assessment Reminder</h2>
                <p>Hi {assessor_name},</p>
                
                <p>This is a reminder that <strong>{prospect_name}</strong> is waiting for their assessment to be completed.</p>
                
                <div style="background-color: #f1f1f1; padding: 15px; border-left: 4px solid #3b82f6;">
                    <p><strong>Prospect:</strong> {prospect_name}</p>
                    <p><strong>Status:</strong> {status}</p>
                    <p><strong>Days in pipeline:</strong> {days_in_review}</p>
                </div>
                
                <p><strong>Next Steps:</strong></p>
                <ol>
                    <li>Log in to the BHH Enrollment Command Center</li>
                    <li>Find {prospect_name} in the prospects list</li>
                    <li>Click "Complete Assessment" to open the rubric</li>
                    <li>Fill out the assessment and submit</li>
                </ol>
                
                <p style="color: #666; font-size: 0.9em;">
                    You'll receive this reminder every 2 business days until the assessment is completed.
                </p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="font-size: 0.85em; color: #999;">
                    This is an automated reminder from the BHH Enrollment System.
                </p>
            </body>
        </html>
        """
        
        # Create email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config.EMAIL_SENDER
        msg["To"] = assessor_email
        
        msg.attach(MIMEText(html_body, "html"))
        
        # Send via Gmail SMTP
        with smtplib.SMTP(config.EMAIL_SMTP_HOST, config.EMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(config.EMAIL_SENDER, gmail_app_password)
            server.send_message(msg)
        
        return {
            "success": True,
            "message": f"✉️  Reminder sent to {assessor_email}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"Email send failed: {str(e)}"
        }


def send_reminder_batch():
    """
    Main function to check for pending assessments and send reminders.
    Designed to be run as a cron job every 2-3 hours.
    
    Returns:
        Summary dict with success count and errors
    """
    if not config.EMAIL_ENABLED:
        return {"success": False, "message": "Email reminders disabled in config"}
    
    try:
        # Fetch all prospects
        notion = notion_io.get_notion_client()
        pages = notion_io.fetch_all_pages_from_databases(notion, config.DATABASES)
        
        # Get pending assessments
        pending = get_pending_assessments(pages)
        if not pending:
            return {"sent": 0, "skipped": 0, "message": "No pending assessments"}
        
        # Load tracking data
        tracking = load_reminder_tracking()
        
        sent_count = 0
        skipped_count = 0
        errors = []
        
        # Send reminders
        for prospect in pending:
            if not should_send_reminder(prospect["page_id"], tracking):
                skipped_count += 1
                continue

            # Skip actually sending if we don't have an assessor email; count as skipped so operator can act.
            if not prospect.get("assessor_email"):
                skipped_count += 1
                print(f"⚠️  Skipping {prospect['prospect_name']} — no assessor email on record")
                continue
            
            result = send_email_reminder(
                prospect["prospect_name"],
                prospect["assessor_email"],
                prospect["assessor_name"],
                prospect["days_in_review"]
            )
            
            if result["success"]:
                # Update tracking
                tracking[prospect["page_id"]] = datetime.now().isoformat()
                sent_count += 1
                print(f"✅ {result['message']}")
            else:
                skipped_count += 1
                errors.append(result["message"])
                print(f"❌ {prospect['prospect_name']}: {result['message']}")
        
        # Save updated tracking
        save_reminder_tracking(tracking)
        
        summary = {
            "sent": sent_count,
            "skipped": skipped_count,
            "pending_total": len(pending),
            "errors": errors,
            "message": f"Sent {sent_count} reminders, skipped {skipped_count}"
        }
        
        return summary
    
    except Exception as e:
        return {
            "success": False,
            "message": f"Batch reminder error: {str(e)}"
        }


def reset_reminder_tracking(prospect_page_id: str = None):
    """
    Reset reminder tracking for a prospect (useful after assessment completed).
    If prospect_page_id is None, reset all.
    """
    tracking = load_reminder_tracking()
    
    if prospect_page_id:
        tracking.pop(prospect_page_id, None)
    else:
        tracking = {}
    
    save_reminder_tracking(tracking)
