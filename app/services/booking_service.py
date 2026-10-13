"""
Booking Service.
Manages demo slot appointment scheduling, past date rejection, slot constraints,
idempotent lead association, and Google Sheets synchronization.
"""
import logging
from datetime import datetime, date
from typing import Any, Dict, Optional, Tuple
import pytz
from flask import current_app
from app.services.supabase_service import supabase_service
from app.services.google_sheets_service import google_sheets_service
from app.services.auth_service import verify_booking_token

logger = logging.getLogger(__name__)


def validate_booking_inputs(
    demo_date_str: str,
    slot_time: str
) -> Tuple[bool, Optional[str], Optional[date]]:
    """
    Validates that demo date is not in the past (based on Asia/Kolkata)
    and that slot_time is one of the four allowed slots.
    """
    if not demo_date_str:
        return False, "Please select a date for your demo class.", None

    try:
        parsed_date = datetime.strptime(demo_date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return False, "Invalid date format. Expected YYYY-MM-DD.", None

    # Compare with today in Asia/Kolkata
    tz_name = current_app.config.get("TIMEZONE", "Asia/Kolkata")
    local_tz = pytz.timezone(tz_name)
    today_local = datetime.now(local_tz).date()

    if parsed_date < today_local:
        return False, "Demo date cannot be in the past. Please select today or a future date.", None

    allowed_slots = current_app.config.get("ALLOWED_SLOT_TIMES", ["13:00", "15:00", "17:00", "19:00"])
    if slot_time not in allowed_slots:
        return False, f"Invalid time slot. Allowed slots: {', '.join(allowed_slots)}.", None

    return True, None, parsed_date


def book_or_reschedule_demo(
    lead_id: str,
    demo_date_str: str,
    slot_time: str,
    meeting_url: Optional[str] = None
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """
    Saves or reschedules a booking for the specified lead.
    Enforces 1 current booking per lead. Synchronizes with Google Sheets.

    Returns:
        (success: bool, booking: Optional[dict], lead: Optional[dict], error_message: Optional[str])
    """
    from app.services.settings_service import set_meeting_url_for_booking, get_meeting_url_for_booking

    # Verify lead exists
    try:
        lead = supabase_service.get_lead_by_id(lead_id)
        if not lead:
            return False, None, None, "Enquiry lead record not found."
    except Exception as exc:
        logger.error("Database error fetching lead for booking: %s", exc)
        return False, None, None, "Service error retrieving your enquiry details."

    # Validate date and time slot
    is_valid, validation_err, validated_date = validate_booking_inputs(demo_date_str, slot_time)
    if not is_valid or not validated_date:
        return False, None, lead, validation_err

    # Upsert booking in Supabase
    success, booking, db_err = supabase_service.upsert_booking(
        lead_id=lead_id,
        demo_date=str(validated_date),
        slot_time=slot_time,
        booking_status="Booked",
    )
    if not success or not booking:
        return False, None, lead, f"Could not reserve demo slot: {db_err}"

    if meeting_url and meeting_url.strip():
        set_meeting_url_for_booking(booking["id"], meeting_url.strip())

    booking["meeting_url"] = get_meeting_url_for_booking(booking["id"])

    # Sync with Google Sheets
    student_name = lead.get("student_name", "Student")
    sheet_synced, sheet_msg = google_sheets_service.sync_booking(booking, student_name)
    if sheet_synced:
        supabase_service.update_booking_sheet_sync(booking["id"], "synced")
        booking["sheet_sync_status"] = "synced"
    else:
        supabase_service.update_booking_sheet_sync(booking["id"], "failed", sheet_msg)
        booking["sheet_sync_status"] = "failed"
        booking["sheet_sync_error"] = sheet_msg

    return True, booking, lead, None


def update_existing_booking_status(
    booking_id: str,
    new_status: str
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Updates status for an existing booking (Booked, Attended, Not Attended)
    and syncs to Google Sheets.
    """
    allowed_statuses = current_app.config.get("BOOKING_STATUSES", ["Booked", "Attended", "Not Attended"])
    if new_status not in allowed_statuses:
        return False, None, f"Invalid booking status. Allowed: {', '.join(allowed_statuses)}"

    booking = supabase_service.get_booking_by_id(booking_id)
    if not booking:
        return False, None, "Booking not found."

    lead = supabase_service.get_lead_by_id(booking["lead_id"])
    student_name = lead.get("student_name", "Student") if lead else "Student"

    success, updated_booking, err = supabase_service.update_booking_status(booking_id, new_status)
    if not success or not updated_booking:
        return False, None, f"Database error updating status: {err}"

    # Sync status change to Google Sheets
    sheet_synced, sheet_msg = google_sheets_service.sync_booking(updated_booking, student_name)
    if sheet_synced:
        supabase_service.update_booking_sheet_sync(booking_id, "synced")
    else:
        supabase_service.update_booking_sheet_sync(booking_id, "failed", sheet_msg)

    return True, updated_booking, None
