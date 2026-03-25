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
        page_properties = matching_page.get("properties", {})
        props_lc_map = {k.lower(): k for k in page_properties.keys()}
        assessor = assessment_data.get("assigned_staff_lead", "Staff")
        today = datetime.now().strftime("%Y-%m-%d")

        def _resolve_property(config_attr: str, aliases=None):
            aliases = aliases or []
            configured_name = getattr(config, config_attr, None)
            candidates = [configured_name] if configured_name else []
            candidates.extend(aliases)

            for candidate in candidates:
                if candidate and candidate in page_properties:
                    return candidate
            for candidate in candidates:
                if candidate and candidate.lower() in props_lc_map:
                    return props_lc_map[candidate.lower()]
            return None

        updated_fields = []

        def _safe_update(update_fn, field_label: str):
            try:
                update_fn()
                updated_fields.append(field_label)
            except Exception:
                pass

        prop_assessment_status = _resolve_property("PROP_ASSESSMENT_STATUS", ["Assessment Status", "Status"])
        prop_assessment_date = _resolve_property("PROP_ASSESSMENT_DATE", ["Assessment Date", "Assessment Date "])
        prop_assessor_name = _resolve_property("PROP_ASSESSOR_NAME", ["Assessor Name"])
        prop_assessment_grade = _resolve_property("PROP_ASSESSMENT_GRADE", ["Assessment Grade", "Assessment  Grade"])
        prop_assessment_average = _resolve_property("PROP_ASSESSMENT_AVERAGE_SCORE", ["Assessment Average Score", "Average Score"])
        prop_assessment_summary = _resolve_property("PROP_ASSESSMENT_SUMMARY_COMMENTS", ["Assessment Summary Comments", "Summary Comments"])
        prop_assessment_next_actions = _resolve_property("PROP_ASSESSMENT_NEXT_ACTIONS", ["Assessment Next Actions", "Next Action", "Next Actions"])
        prop_assessment_action_owner = _resolve_property("PROP_ASSESSMENT_ACTION_OWNER", ["Assessment Action Owner", "Action Owner"])
        prop_assessment_target_date = _resolve_property("PROP_ASSESSMENT_TARGET_DATE", ["Assessment Target Date", "Target Date"])
        prop_assessment_payload_json = _resolve_property("PROP_ASSESSMENT_PAYLOAD_JSON", ["Assessment Payload JSON", "Assessment JSON", "Assessment Details"])
        
        # Update Assessment Status to Completed
        if prop_assessment_status:
            _safe_update(
                lambda: notion_io.update_page_select(notion, page_id, prop_assessment_status, "Completed"),
                prop_assessment_status,
            )
        
        # Update Assessment Date
        if prop_assessment_date:
            _safe_update(
                lambda: notion_io.update_page_date(notion, page_id, prop_assessment_date, today),
                prop_assessment_date,
            )
        
        # Update Assessor Name
        if prop_assessor_name:
            _safe_update(
                lambda: notion_io.update_page_rich_text(notion, page_id, prop_assessor_name, assessor),
                prop_assessor_name,
            )
        
        # Update Assessment Grade (1-5 select)
        if prop_assessment_grade:
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
                _safe_update(
                    lambda: notion_io.update_page_select(notion, page_id, prop_assessment_grade, grade_display),
                    prop_assessment_grade,
                )

        if prop_assessment_average:
            avg_score = assessment_data.get("average_score")
            if isinstance(avg_score, (int, float)):
                _safe_update(
                    lambda: notion_io.update_page_number(notion, page_id, prop_assessment_average, float(avg_score)),
                    prop_assessment_average,
                )

        if prop_assessment_summary:
            summary_comments = assessment_data.get("summary_comments", "")
            if summary_comments:
                _safe_update(
                    lambda: notion_io.update_page_rich_text(notion, page_id, prop_assessment_summary, summary_comments),
                    prop_assessment_summary,
                )

        if prop_assessment_action_owner:
            action_owner = assessment_data.get("action_owner", "")
            if action_owner:
                _safe_update(
                    lambda: notion_io.update_page_rich_text(notion, page_id, prop_assessment_action_owner, action_owner),
                    prop_assessment_action_owner,
                )

        if prop_assessment_target_date:
            target_date = assessment_data.get("target_date", "")
            if target_date:
                _safe_update(
                    lambda: notion_io.update_page_date(notion, page_id, prop_assessment_target_date, target_date),
                    prop_assessment_target_date,
                )

        if prop_assessment_next_actions:
            next_actions = assessment_data.get("next_actions", []) or []
            if next_actions:
                next_actions_prop = page_properties.get(prop_assessment_next_actions, {})
                if next_actions_prop.get("type") == "multi_select":
                    _safe_update(
                        lambda: notion_io.update_page_property(
                            notion,
                            page_id,
                            prop_assessment_next_actions,
                            {"multi_select": [{"name": str(action)} for action in next_actions]},
                        ),
                        prop_assessment_next_actions,
                    )
                else:
                    _safe_update(
                        lambda: notion_io.update_page_rich_text(notion, page_id, prop_assessment_next_actions, ", ".join(str(action) for action in next_actions)),
                        prop_assessment_next_actions,
                    )

        if prop_assessment_payload_json:
            payload_json = json.dumps(assessment_data, indent=2)
            chunks = [payload_json[i:i + 1900] for i in range(0, len(payload_json), 1900)]
            rich_text_payload = {"rich_text": [{"type": "text", "text": {"content": chunk}} for chunk in chunks[:8]]}
            _safe_update(
                lambda: notion_io.update_page_property(notion, page_id, prop_assessment_payload_json, rich_text_payload),
                prop_assessment_payload_json,
            )
        
        # Clear reminder tracking for this prospect (assessment completed)
        if getattr(config, "EMAIL_ENABLED", False):
            email_reminders.reset_reminder_tracking(page_id)
        
        return {
            "success": True,
            "page_id": page_id,
            "message": f"Assessment saved for {prospect_name}" + (f" (updated: {', '.join(updated_fields)})" if updated_fields else "")
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
