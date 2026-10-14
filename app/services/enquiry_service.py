"""
Enquiry Service.
Orchestrates student enquiry validation, canonical phone normalization,
duplicate lead prevention, Supabase storage, and Google Sheets synchronization.
"""
import logging
from typing import Any, Dict, Optional, Tuple
from email_validator import validate_email, EmailNotValidError
from flask import current_app
from app.services.phone_service import normalize_phone_number
from app.services.supabase_service import supabase_service
from app.services.google_sheets_service import google_sheets_service
from app.services.auth_service import generate_booking_token

logger = logging.getLogger(__name__)


def validate_enquiry_payload(form_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validates enquiry form fields thoroughly on the server.
    Ensures name, normalized phone, email, class, exam goal, and course meet constraints.
    """
    # 1. Honeypot check (anti-spam)
    honeypot = form_data.get("website_url_check", "").strip()
    if honeypot:
        logger.warning("Spam bot detected via honeypot field.")
        return False, "Automated submission rejected.", None

    # 2. Student Name
    name = form_data.get("student_name", "").strip()
    if not name or len(name) < 2:
        return False, "Student Name is required (minimum 2 characters).", None
    if len(name) > 100:
        return False, "Student Name must not exceed 100 characters.", None

    # 3. Phone Number & Normalization (Strict Indian phone enforcement)
    raw_phone = form_data.get("phone_number", "").strip()
    is_valid_phone, phone_e164, _ = normalize_phone_number(raw_phone, require_indian=True)
    if not is_valid_phone:
        return False, phone_e164, None  # phone_e164 holds error message if invalid

    # 4. Email validation
    raw_email = form_data.get("email", "").strip()
    if not raw_email:
        return False, "Email address is required.", None
    try:
        valid_email_info = validate_email(raw_email, check_deliverability=False)
        normalized_email = valid_email_info.normalized.lower()
    except EmailNotValidError as err:
        return False, f"Invalid email address: {str(err)}", None

    # 5. Class validation
    class_level = form_data.get("class_level", "").strip()
    allowed_classes = current_app.config.get("ALLOWED_CLASSES", ["11", "12"])
    if class_level not in allowed_classes:
        return False, f"Class must be one of: {', '.join(allowed_classes)}.", None

    # 6. Exam Goal validation
    exam_goal = form_data.get("exam_goal", "").strip().upper()
    allowed_goals = current_app.config.get("ALLOWED_EXAM_GOALS", ["NEET", "JEE"])
    if exam_goal not in allowed_goals:
        return False, f"Exam goal must be one of: {', '.join(allowed_goals)}.", None

    # 7. Interested Course validation (must match target exam goal)
    interested_course = form_data.get("interested_course", "").strip()
    course_options = current_app.config.get("COURSE_OPTIONS", [])
    if interested_course not in course_options:
        return False, "Please select a valid course option from the list.", None

    exam_courses = current_app.config.get("EXAM_COURSES", {})
    allowed_for_goal = exam_courses.get(exam_goal, [])
    # If the course is goal-specific, make sure it matches the selected goal
    if allowed_for_goal and interested_course not in allowed_for_goal and interested_course not in ["Foundation Course", "Other"]:
        return False, f"Selected course '{interested_course}' does not match your target exam goal ({exam_goal}). Please choose a {exam_goal} course.", None

    validated = {
        "student_name": name,
        "phone_e164": phone_e164,
        "email": normalized_email,
        "class_level": class_level,
        "exam_goal": exam_goal,
        "interested_course": interested_course,
    }
    return True, None, validated


def process_student_enquiry(
    form_data: Dict[str, Any]
) -> Tuple[bool, bool, Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Executes the complete enquiry creation workflow.

    Returns:
        (
            success: bool,
            is_duplicate: bool,
            lead: Optional[dict],
            booking_token: Optional[str],
            message: Optional[str]
        )
    """
    is_valid, validation_error, validated_data = validate_enquiry_payload(form_data)
    if not is_valid or not validated_data:
        return False, False, None, None, validation_error

    secret_key = current_app.config.get("SECRET_KEY", "kmie-secret")

    # Step 1: Pre-check duplicate lead by canonical phone number
    try:
        existing_lead = supabase_service.find_lead_by_phone(validated_data["phone_e164"])
        if existing_lead:
            logger.info("Found existing lead %s for phone %s", existing_lead["id"], validated_data["phone_e164"])
            token = generate_booking_token(existing_lead["id"], secret_key)
            return (
                False,
                True,
                existing_lead,
                token,
                "An enquiry with this phone number has already been registered with KMIE.",
            )
    except Exception as exc:
        logger.error("Supabase error checking existing phone: %s", exc)
        return False, False, None, None, "Service temporarily unavailable. Please try again in a few moments."

    # Step 2: Persist new lead to Supabase
    success, new_lead, err = supabase_service.create_lead(validated_data)
    if not success or not new_lead:
        if err == "DUPLICATE_PHONE":
            # Concurrent race condition caught by database unique constraint
            existing = supabase_service.find_lead_by_phone(validated_data["phone_e164"])
            lead_id = existing["id"] if existing else ""
            token = generate_booking_token(lead_id, secret_key) if lead_id else None
            return (
                False,
                True,
                existing,
                token,
                "An enquiry with this phone number has already been registered with KMIE.",
            )
        return False, False, None, None, f"Could not record enquiry: {err}"

    # Step 3: Attempt Google Sheets synchronization
    sheet_synced, sheet_msg = google_sheets_service.sync_lead(new_lead)
    if sheet_synced:
        supabase_service.update_lead_sheet_sync(new_lead["id"], "synced")
        new_lead["sheet_sync_status"] = "synced"
    else:
        supabase_service.update_lead_sheet_sync(new_lead["id"], "failed", sheet_msg)
        new_lead["sheet_sync_status"] = "failed"
        new_lead["sheet_sync_error"] = sheet_msg

    # Step 4: Issue signed booking token for proceeding to demo scheduling
    booking_token = generate_booking_token(new_lead["id"], secret_key)

    return True, False, new_lead, booking_token, "Enquiry submitted successfully."
