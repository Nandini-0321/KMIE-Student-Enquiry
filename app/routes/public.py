"""
Public Routes for Student Enquiry Submission and Result Display.
"""
from datetime import datetime
import pytz
from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash
from app.services.enquiry_service import process_student_enquiry
from app.services.phone_service import mask_phone_number, normalize_phone_number
from app.services.auth_service import generate_booking_token
from app.services.supabase_service import supabase_service
from app.services.settings_service import get_meeting_url_for_booking

public_bp = Blueprint("public", __name__)


@public_bp.route("/", methods=["GET"])
def index():
    """Renders the primary student enquiry form."""
    courses = current_app.config.get("COURSE_OPTIONS", [])
    classes = current_app.config.get("ALLOWED_CLASSES", ["11", "12"])
    exam_goals = current_app.config.get("ALLOWED_EXAM_GOALS", ["NEET", "JEE"])

    return render_template(
        "index.html",
        courses=courses,
        classes=classes,
        exam_goals=exam_goals,
        form_data={},
    )


@public_bp.route("/enquire", methods=["POST"])
def submit_enquiry():
    """Processes student enquiry form submission."""
    form_data = {
        "student_name": request.form.get("student_name", ""),
        "phone_number": request.form.get("phone_number", ""),
        "email": request.form.get("email", ""),
        "class_level": request.form.get("class_level", ""),
        "exam_goal": request.form.get("exam_goal", ""),
        "interested_course": request.form.get("interested_course", ""),
        "website_url_check": request.form.get("website_url_check", ""),  # honeypot
    }

    success, is_duplicate, lead, booking_token, message = process_student_enquiry(form_data)

    if not success and not is_duplicate:
        # Validation error or temporary database fault
        flash(message or "Please correct the errors in the form.", "danger")
        return render_template(
            "index.html",
            courses=current_app.config.get("COURSE_OPTIONS", []),
            classes=current_app.config.get("ALLOWED_CLASSES", ["11", "12"]),
            exam_goals=current_app.config.get("ALLOWED_EXAM_GOALS", ["NEET", "JEE"]),
            form_data=form_data,
            error_message=message,
        ), 400

    masked_phone = mask_phone_number(lead.get("phone_e164", "")) if lead else ""

    # If this lead already has a demo booking, load the booking details & meeting URL
    existing_booking = None
    booking_meeting_url = None
    formatted_demo_date = None
    formatted_demo_time = None
    slot_labels = current_app.config.get("SLOT_TIME_LABELS", {})

    if lead and lead.get("id"):
        try:
            existing_booking = supabase_service.get_booking_by_lead_id(lead["id"])
            if existing_booking:
                booking_meeting_url = get_meeting_url_for_booking(existing_booking.get("id"))
                demo_date_str = str(existing_booking.get("demo_date", ""))
                try:
                    date_obj = datetime.strptime(demo_date_str, "%Y-%m-%d")
                    formatted_demo_date = date_obj.strftime("%A, %d %B %Y")
                except Exception:
                    formatted_demo_date = demo_date_str
                slot_code = existing_booking.get("slot_time", "")
                formatted_demo_time = slot_labels.get(slot_code, slot_code)
        except Exception as exc:
            current_app.logger.warning("Error fetching booking details for enquiry lead: %s", exc)

    return render_template(
        "enquiry_result.html",
        success=success,
        is_duplicate=is_duplicate,
        lead=lead,
        masked_phone=masked_phone,
        booking_token=booking_token,
        existing_booking=existing_booking,
        booking_meeting_url=booking_meeting_url,
        formatted_demo_date=formatted_demo_date,
        formatted_demo_time=formatted_demo_time,
        slot_labels=slot_labels,
        message=message,
    )


@public_bp.route("/check-status", methods=["GET", "POST"])
def check_status():
    """Allows students to check their existing registration and demo appointment meeting link."""
    if request.method == "GET":
        return redirect(url_for("public.index"))

    phone_input = request.form.get("phone_number", "").strip()
    is_valid, phone_e164, err_msg = normalize_phone_number(phone_input)

    if not is_valid or not phone_e164:
        flash(err_msg or "Please enter a valid phone number to check your demo status.", "warning")
        return redirect(url_for("public.index"))

    try:
        lead = supabase_service.get_lead_by_phone(phone_e164)
    except Exception as exc:
        current_app.logger.error("Error looking up student by phone: %s", exc)
        lead = None

    if not lead:
        flash(f"No existing enquiry found for phone number {phone_input}. Please submit the enquiry form below to register.", "info")
        return redirect(url_for("public.index"))

    # Generate fresh booking token for rescheduling
    secret_key = current_app.config.get("SECRET_KEY", "kmie-secret")
    booking_token = generate_booking_token(lead["id"], secret_key)
    masked_phone = mask_phone_number(lead.get("phone_e164", ""))

    existing_booking = None
    booking_meeting_url = None
    formatted_demo_date = None
    formatted_demo_time = None
    slot_labels = current_app.config.get("SLOT_TIME_LABELS", {})

    try:
        existing_booking = supabase_service.get_booking_by_lead_id(lead["id"])
        if existing_booking:
            booking_meeting_url = get_meeting_url_for_booking(existing_booking.get("id"))
            demo_date_str = str(existing_booking.get("demo_date", ""))
            try:
                date_obj = datetime.strptime(demo_date_str, "%Y-%m-%d")
                formatted_demo_date = date_obj.strftime("%A, %d %B %Y")
            except Exception:
                formatted_demo_date = demo_date_str
            slot_code = existing_booking.get("slot_time", "")
            formatted_demo_time = slot_labels.get(slot_code, slot_code)
    except Exception as exc:
        current_app.logger.warning("Error fetching booking details in check-status: %s", exc)

    return render_template(
        "enquiry_result.html",
        success=True,
        is_duplicate=True,
        lead=lead,
        masked_phone=masked_phone,
        booking_token=booking_token,
        existing_booking=existing_booking,
        booking_meeting_url=booking_meeting_url,
        formatted_demo_date=formatted_demo_date,
        formatted_demo_time=formatted_demo_time,
        slot_labels=slot_labels,
        message="Registration verified. Here are your enquiry and live demo appointment details.",
    )
