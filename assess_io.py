"""
Assessment I/O module for saving rubric assessments to Notion and Google Drive.
"""
import json
import os
from datetime import datetime
import config
import notion_io
import email_reminders


def save_assessment_to_notion(prospect_name: str, assessment_data: dict, config):
    """
    Save assessment to a prospect's Notion page.
    
    Finds the prospect by name in the Notion databases and updates:
    - Assessment Status → "Completed"
    - Assessment Date → today's ISO date
    - Assessor Name → from assessment_data
    - Notion rubric score fields (if present in assessment_data)
    
    Args:
        prospect_name: Name of the prospect (must match Notion record)
        assessment_data: Dict with assessment results (from rubric form)
        config: Config module with property names
    
    Returns:
        Dict with {success: bool, page_id: str, message: str}
    """
    try:
        notion = notion_io.get_notion_client()
        pages = notion_io.fetch_all_pages_from_databases(notion, config.DATABASES)
        
        # Find matching prospect by name
        matching_page = None
        for page in pages:
            from extractors import get_title
            if get_title(page.get("properties", {})) == prospect_name:
                matching_page = page
                break
        
        if not matching_page:
            return {
                "success": False,
                "message": f"Could not find prospect '{prospect_name}' in Notion"
            }
        
        page_id = matching_page["id"]
        assessor = assessment_data.get("assigned_staff_lead", "Staff")
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Update Assessment Status to Completed
        if hasattr(config, "PROP_ASSESSMENT_STATUS"):
            notion_io.update_page_select(notion, page_id, config.PROP_ASSESSMENT_STATUS, "Completed")
        
        # Update Assessment Date
        if hasattr(config, "PROP_ASSESSMENT_DATE"):
            notion_io.update_page_date(notion, page_id, config.PROP_ASSESSMENT_DATE, today)
        
        # Update Assessor Name
        if hasattr(config, "PROP_ASSESSOR_NAME"):
            notion_io.update_page_rich_text(notion, page_id, config.PROP_ASSESSOR_NAME, assessor)
        
        # Update Assessment Grade (1-5 select)
        if hasattr(config, "PROP_ASSESSMENT_GRADE"):
            grade_value = str(assessment_data.get("overall_rating", ""))
            if grade_value and grade_value != "0":
                # Map rating to grade display
                grade_map = {
                    "5": "5 - A Rated",
                    "4": "4 - Strong Fit",
                    "3": "3 - Possible",
                    "2": "2 - Marginal",
                    "1": "1 - Poor Fit",
                }
                grade_display = grade_map.get(grade_value, grade_value)
                notion_io.update_page_select(notion, page_id, config.PROP_ASSESSMENT_GRADE, grade_display)
        
        # Clear reminder tracking for this prospect (assessment completed)
        if getattr(config, "EMAIL_ENABLED", False):
            email_reminders.reset_reminder_tracking(page_id)
        
        return {
            "success": True,
            "page_id": page_id,
            "message": f"Assessment saved for {prospect_name}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"Error saving to Notion: {str(e)}"
        }


def export_assessment_to_drive(prospect_name: str, assessment_data: dict, folder_path: str = None):
    """
    Export assessment as JSON to Google Drive or local filesystem.
    
    Args:
        prospect_name: Name of prospect (used in filename)
        assessment_data: Full assessment dict
        folder_path: Optional path to save locally. If None, returns JSON string.
    
    Returns:
        Dict with {success: bool, path: str, message: str}
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = prospect_name.replace(" ", "_").lower()
        filename = f"assessment_{safe_name}_{timestamp}.json"
        
        if folder_path:
            os.makedirs(folder_path, exist_ok=True)
            filepath = os.path.join(folder_path, filename)
            with open(filepath, "w") as f:
                json.dump(assessment_data, f, indent=2)
            return {
                "success": True,
                "path": filepath,
                "message": f"Assessment exported to {filepath}"
            }
        else:
            # Return JSON string if no folder specified
            return {
                "success": True,
                "path": None,
                "data": json.dumps(assessment_data, indent=2),
                "message": "Assessment ready for export"
            }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"Error exporting assessment: {str(e)}"
        }


def get_assessment_revision_count(page_id: str, notion_client=None) -> int:
    """
    Get count of revisions for a prospect's assessment.
    Currently returns 1 if assessment exists, 0 otherwise.
    Future: track versions in Notion database or Drive.
    """
    # Placeholder for future revision tracking
    return 0
