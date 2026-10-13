"""
Demo Booking Routes.
Manages demo appointment selection, signed token authorization, and confirmation.
"""
from datetime import datetime
import pytz
from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash
from app.services.auth_service import verify_booking_token
from app.services.booking_service import book_or_reschedule_demo
from app.services.supabase_service import supabase_service
from app.services.phone_service import mask_phone_number
from app.services.settings_service import get_meeting_url_for_booking

booking_bp = Blueprint("booking", __name__)


@booking_bp.route("/book-demo", methods=["GET"])
def select_slot():
    """Renders the demo appointment selection interface."""
    token = request.args.get("token", "").strip()
    secret_key = current_app.config.get("SECRET_KEY", "kmie-secret")

    is_valid, lead_id, err_msg = verify_booking_token(token, secret_key)
    if not is_valid or not lead_id:
        flash(err_msg or "Invalid or expired booking link. Please submit a new enquiry.", "danger")
        return redirect(url_for("public.index"))

    try:
        lead = supabase_service.get_lead_by_id(lead_id)
        if not lead:
            flash("Enquiry lead record could not be found.", "danger")
            return redirect(url_for("public.index"))
        existing_booking = supabase_service.get_booking_by_lead_id(lead_id)
    except Exception:
        flash("Could not retrieve enquiry details. Please try again.", "danger")
        return redirect(url_for("public.index"))

    # Compute today's date in Asia/Kolkata for client date-picker constraint
    tz_name = current_app.config.get("TIMEZONE", "Asia/Kolkata")
    local_tz = pytz.timezone(tz_name)
    min_date = datetime.now(local_tz).strftime("%Y-%m-%d")

    slot_times = current_app.config.get("ALLOWED_SLOT_TIMES", ["13:00", "15:00", "17:00", "19:00"])
    slot_labels = current_app.config.get("SLOT_TIME_LABELS", {})

    booking_meeting_url = None
    if existing_booking:
        booking_meeting_url = get_meeting_url_for_booking(existing_booking.get("id"))

    return render_template(
        "booking.html",
        token=token,
        lead=lead,
        existing_booking=existing_booking,
        booking_meeting_url=booking_meeting_url,
        min_date=min_date,
        slot_times=slot_times,
        slot_labels=slot_labels,
    )


@booking_bp.route("/book-demo", methods=["POST"])
def confirm_booking():
    """Processes demo slot booking or rescheduling."""
    token = request.form.get("token", "").strip()
    demo_date = request.form.get("demo_date", "").strip()
    slot_time = request.form.get("slot_time", "").strip()
    secret_key = current_app.config.get("SECRET_KEY", "kmie-secret")

    is_valid, lead_id, err_msg = verify_booking_token(token, secret_key)
    if not is_valid or not lead_id:
        flash(err_msg or "Booking session has expired.", "danger")
        return redirect(url_for("public.index"))

    success, booking, lead, book_err = book_or_reschedule_demo(lead_id, demo_date, slot_time)
    if not success or not booking:
        flash(book_err or "Could not schedule demo slot. Please check the date and time.", "danger")
        # Re-render booking page with error
        tz_name = current_app.config.get("TIMEZONE", "Asia/Kolkata")
        min_date = datetime.now(pytz.timezone(tz_name)).strftime("%Y-%m-%d")
        slot_times = current_app.config.get("ALLOWED_SLOT_TIMES", ["13:00", "15:00", "17:00", "19:00"])
        slot_labels = current_app.config.get("SLOT_TIME_LABELS", {})
        existing_booking = supabase_service.get_booking_by_lead_id(lead_id) if lead_id else None
        return render_template(
            "booking.html",
            token=token,
            lead=lead or {},
            existing_booking=existing_booking,
            min_date=min_date,
            slot_times=slot_times,
            slot_labels=slot_labels,
            error_message=book_err,
        ), 400

    return redirect(url_for("booking.confirmation", token=token, booking_id=booking["id"]))


@booking_bp.route("/booking-confirmation", methods=["GET"])
def confirmation():
    """Renders the final booking confirmation page."""
    token = request.args.get("token", "").strip()
    booking_id = request.args.get("booking_id", "").strip()
    secret_key = current_app.config.get("SECRET_KEY", "kmie-secret")

    is_valid, lead_id, _ = verify_booking_token(token, secret_key)
    if not is_valid or not lead_id:
        flash("Invalid or expired session. Please visit the homepage to check your enquiry.", "warning")
        return redirect(url_for("public.index"))

    try:
        lead = supabase_service.get_lead_by_id(lead_id)
        booking = supabase_service.get_booking_by_id(booking_id) if booking_id else supabase_service.get_booking_by_lead_id(lead_id)
        if not lead or not booking:
            flash("Booking record not found.", "danger")
            return redirect(url_for("public.index"))
    except Exception:
        flash("Unable to load booking confirmation details.", "danger")
        return redirect(url_for("public.index"))

    # Format human-readable date and time
    demo_date_str = str(booking.get("demo_date", ""))
    try:
        date_obj = datetime.strptime(demo_date_str, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%A, %d %B %Y")
    except Exception:
        formatted_date = demo_date_str

    slot_time = booking.get("slot_time", "")
    slot_labels = current_app.config.get("SLOT_TIME_LABELS", {})
    formatted_time = f"{slot_labels.get(slot_time, slot_time)} ({slot_time})"

    from app.services.settings_service import get_meeting_url_for_booking
    demo_meeting_url = get_meeting_url_for_booking(booking.get("id"))

    return render_template(
        "booking_confirmation.html",
        lead=lead,
        booking=booking,
        formatted_date=formatted_date,
        formatted_time=formatted_time,
        demo_meeting_url=demo_meeting_url,
        masked_phone=mask_phone_number(lead.get("phone_e164", "")),
        token=token,
    )
