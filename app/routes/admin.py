"""
Admin Dashboard Routes.
Handles administrative authentication, lead management, booking rescheduling,
status updates (Booked/Attended/Not Attended), and Google Sheets sync retry actions.
"""
from datetime import datetime
import pytz
from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash
from app.services.auth_service import (
    verify_admin_password,
    login_admin,
    logout_admin,
    admin_required,
)
from app.services.supabase_service import supabase_service
from app.services.google_sheets_service import google_sheets_service
from app.services.booking_service import book_or_reschedule_demo, update_existing_booking_status

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """Administrator login page and credential verification."""
    expected_username = current_app.config.get("ADMIN_USERNAME", "")
    expected_hash = current_app.config.get("ADMIN_PASSWORD_HASH", "")

    if not expected_username or not expected_hash:
        flash("Administrator access is currently disabled because credentials have not been configured in the environment.", "warning")
        return render_template("admin_login.html", is_configured=False)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if verify_admin_password(username, password, expected_username, expected_hash):
            login_admin(username)
            flash("Welcome to the KMIE Administration Dashboard.", "success")
            next_url = request.args.get("next") or url_for("admin.dashboard")
            return redirect(next_url)
        else:
            flash("Invalid administrator username or password.", "danger")

    return render_template("admin_login.html", is_configured=True)


@admin_bp.route("/logout", methods=["POST"])
def logout():
    """Logs out the administrator."""
    logout_admin()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    """Primary administrator dashboard view."""
    search_query = request.args.get("search", "").strip()
    exam_goal = request.args.get("exam_goal", "").strip()
    class_level = request.args.get("class_level", "").strip()
    sync_status = request.args.get("sync_status", "").strip()

    try:
        leads = supabase_service.list_all_leads_with_bookings(
            search_query=search_query or None,
            exam_goal=exam_goal or None,
            class_level=class_level or None,
            sync_status=sync_status or None,
        )
        metrics = supabase_service.get_dashboard_metrics()
    except Exception as exc:
        flash(f"Error loading dashboard data: {str(exc)}", "danger")
        leads = []
        metrics = {
            "total_leads": 0,
            "total_bookings": 0,
            "attended_bookings": 0,
            "not_attended_bookings": 0,
            "booked_bookings": 0,
            "pending_sync_count": 0,
        }

    tz_name = current_app.config.get("TIMEZONE", "Asia/Kolkata")
    min_date = datetime.now(pytz.timezone(tz_name)).strftime("%Y-%m-%d")
    from app.services.settings_service import get_global_meeting_url
    global_meeting_url = get_global_meeting_url()

    return render_template(
        "admin_dashboard.html",
        leads=leads,
        metrics=metrics,
        search_query=search_query,
        exam_goal=exam_goal,
        class_level=class_level,
        sync_status=sync_status,
        min_date=min_date,
        global_meeting_url=global_meeting_url,
        slot_times=current_app.config.get("ALLOWED_SLOT_TIMES", []),
        slot_labels=current_app.config.get("SLOT_TIME_LABELS", {}),
        booking_statuses=current_app.config.get("BOOKING_STATUSES", []),
    )


@admin_bp.route("/settings/meeting-url", methods=["POST"])
@admin_required
def update_meeting_url():
    """Updates the global demo class meeting link."""
    new_url = request.form.get("meeting_url", "").strip()
    if not new_url:
        flash("Meeting URL cannot be empty.", "warning")
    else:
        from app.services.settings_service import update_global_meeting_url
        update_global_meeting_url(new_url)
        flash("Demo class meeting link updated successfully! Students will now see this link.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/bookings/<booking_id>/status", methods=["POST"])
@admin_required
def update_status(booking_id):
    """Updates booking status to Booked, Attended, or Not Attended."""
    new_status = request.form.get("status", "").strip()
    success, _, err = update_existing_booking_status(booking_id, new_status)
    if success:
        flash(f"Booking status updated to '{new_status}' and synchronization triggered.", "success")
    else:
        flash(f"Could not update status: {err}", "danger")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/leads/<lead_id>/book", methods=["POST"])
@admin_required
def admin_schedule_booking(lead_id):
    """Admin-triggered booking or rescheduling for a lead."""
    demo_date = request.form.get("demo_date", "").strip()
    slot_time = request.form.get("slot_time", "").strip()
    meeting_url = request.form.get("meeting_url", "").strip()

    success, _, _, err = book_or_reschedule_demo(lead_id, demo_date, slot_time, meeting_url=meeting_url)
    if success:
        flash("Demo booking scheduled/updated successfully.", "success")
    else:
        flash(f"Could not book demo: {err}", "danger")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/sync/retry/<record_type>/<record_id>", methods=["POST"])
@admin_required
def retry_single_sync(record_type, record_id):
    """Retries Google Sheets synchronization for a single lead or booking."""
    if record_type == "lead":
        lead = supabase_service.get_lead_by_id(record_id)
        if not lead:
            flash("Lead not found for retry.", "danger")
            return redirect(url_for("admin.dashboard"))

        synced, msg = google_sheets_service.sync_lead(lead)
        if synced:
            supabase_service.update_lead_sheet_sync(record_id, "synced")
            flash(f"Lead successfully synced to Google Sheets: {msg}", "success")
        else:
            supabase_service.update_lead_sheet_sync(record_id, "failed", msg)
            flash(f"Retry failed for lead: {msg}", "danger")

    elif record_type == "booking":
        booking = supabase_service.get_booking_by_id(record_id)
        if not booking:
            flash("Booking not found for retry.", "danger")
            return redirect(url_for("admin.dashboard"))

        lead = supabase_service.get_lead_by_id(booking["lead_id"])
        student_name = lead.get("student_name", "Student") if lead else "Student"

        synced, msg = google_sheets_service.sync_booking(booking, student_name)
        if synced:
            supabase_service.update_booking_sheet_sync(record_id, "synced")
            flash(f"Booking successfully synced to Google Sheets: {msg}", "success")
        else:
            supabase_service.update_booking_sheet_sync(record_id, "failed", msg)
            flash(f"Retry failed for booking: {msg}", "danger")
    else:
        flash("Invalid record type for sync.", "warning")

    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/sync/retry-all", methods=["POST"])
@admin_required
def retry_all_pending_sync():
    """Retries synchronization for all pending/failed leads and bookings in batch."""
    pending_leads, pending_bookings = supabase_service.get_pending_sync_items()
    synced_leads_count = 0
    synced_bookings_count = 0
    errors = []

    for lead in pending_leads:
        synced, msg = google_sheets_service.sync_lead(lead)
        if synced:
            supabase_service.update_lead_sheet_sync(lead["id"], "synced")
            synced_leads_count += 1
        else:
            supabase_service.update_lead_sheet_sync(lead["id"], "failed", msg)
            errors.append(f"Lead {lead['id'][:8]}: {msg}")

    for booking in pending_bookings:
        lead_info = booking.get("leads", {})
        student_name = lead_info.get("student_name", "Student") if isinstance(lead_info, dict) else "Student"
        synced, msg = google_sheets_service.sync_booking(booking, student_name)
        if synced:
            supabase_service.update_booking_sheet_sync(booking["id"], "synced")
            synced_bookings_count += 1
        else:
            supabase_service.update_booking_sheet_sync(booking["id"], "failed", msg)
            errors.append(f"Booking {booking['id'][:8]}: {msg}")

    total_synced = synced_leads_count + synced_bookings_count
    if errors:
        flash(f"Synchronized {total_synced} records. Encountered {len(errors)} issues: {'; '.join(errors[:2])}", "warning")
    else:
        flash(f"Successfully synchronized all {total_synced} pending records to Google Sheets.", "success")

    return redirect(url_for("admin.dashboard"))
