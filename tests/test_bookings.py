"""
Tests for Demo Booking Workflow, Validation, Rescheduling, and Status Updates.
Verifies Requirements:
- 12. Valid date and time slot booking
- 13. Rejection of a past demo date
- 14. Rejection of an unsupported time
- 15. Correct lead-to-booking association
- 16. Existing booking rescheduling
- 17. Booking status validation and updates
- 19. Confirmation message correctness
"""
from datetime import datetime, timedelta
import pytz
import pytest
from app.services.booking_service import (
    validate_booking_inputs,
    book_or_reschedule_demo,
    update_existing_booking_status,
)
from app.services.auth_service import generate_booking_token


class TestDemoBookings:
    """Test suite for booking operations."""

    def test_valid_date_and_time_booking(self, app, mock_supabase, mock_sheets):
        """12. Verifies booking demo slot on a valid future date and supported time."""
        with app.app_context():
            # Setup lead
            lead_id = "lead-uuid-1"
            mock_supabase["leads"][lead_id] = {
                "id": lead_id,
                "student_name": "Kavya Reddy",
                "phone_e164": "+919876543210",
                "email": "kavya@example.com",
                "class_level": "11",
                "exam_goal": "NEET",
                "interested_course": "NEET Long-Term Preparation",
            }

            future_date = (datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(days=2)).strftime("%Y-%m-%d")
            success, booking, lead, err = book_or_reschedule_demo(lead_id, future_date, "15:00")

            assert success is True
            assert booking is not None
            assert booking["lead_id"] == lead_id
            assert booking["demo_date"] == future_date
            assert booking["slot_time"] == "15:00"
            assert booking["booking_status"] == "Booked"

    def test_rejection_of_past_demo_date(self, app):
        """13. Verifies that demo dates in the past are rejected."""
        with app.app_context():
            past_date = (datetime.now(pytz.timezone("Asia/Kolkata")) - timedelta(days=1)).strftime("%Y-%m-%d")
            ok, err, _ = validate_booking_inputs(past_date, "13:00")

            assert ok is False
            assert "cannot be in the past" in err

    def test_rejection_of_unsupported_time_slot(self, app):
        """14. Verifies that unsupported slot times are rejected."""
        with app.app_context():
            future_date = (datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(days=1)).strftime("%Y-%m-%d")
            invalid_slots = ["10:00", "12:00", "14:30", "20:00", "invalid"]

            for slot in invalid_slots:
                ok, err, _ = validate_booking_inputs(future_date, slot)
                assert ok is False
                assert "Invalid time slot" in err

    def test_correct_lead_association(self, app, mock_supabase, mock_sheets):
        """15. Verifies that booking is strictly tied to the correct lead ID."""
        with app.app_context():
            lead_id = "lead-target-42"
            mock_supabase["leads"][lead_id] = {
                "id": lead_id,
                "student_name": "Target Student",
                "phone_e164": "+919876599999",
                "email": "target@example.com",
            }
            future_date = (datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(days=3)).strftime("%Y-%m-%d")
            success, booking, _, _ = book_or_reschedule_demo(lead_id, future_date, "17:00")

            assert success is True
            assert booking["lead_id"] == lead_id

    def test_existing_booking_rescheduling(self, app, mock_supabase, mock_sheets):
        """
        16. Verifies that booking again for the same lead updates the existing booking
        instead of creating a second booking record.
        """
        with app.app_context():
            lead_id = "lead-reschedule-1"
            mock_supabase["leads"][lead_id] = {
                "id": lead_id,
                "student_name": "Siddharth",
                "phone_e164": "+919876541111",
                "email": "sid@example.com",
            }
            date1 = (datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(days=1)).strftime("%Y-%m-%d")
            date2 = (datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(days=4)).strftime("%Y-%m-%d")

            # First booking
            s1, b1, _, _ = book_or_reschedule_demo(lead_id, date1, "13:00")
            assert s1 is True
            booking_id_initial = b1["id"]

            # Reschedule to date2, 19:00
            s2, b2, _, _ = book_or_reschedule_demo(lead_id, date2, "19:00")
            assert s2 is True
            assert b2["id"] == booking_id_initial  # Same booking record updated
            assert b2["demo_date"] == date2
            assert b2["slot_time"] == "19:00"

            # Verify only 1 booking exists in the database
            assert len(mock_supabase["bookings"]) == 1

    def test_booking_status_validation_and_updates(self, app, mock_supabase, mock_sheets):
        """17. Verifies that booking status can be updated to Booked, Attended, or Not Attended."""
        with app.app_context():
            # Setup lead and booking
            lead_id = "lead-status-test"
            mock_supabase["leads"][lead_id] = {"id": lead_id, "student_name": "Priya", "phone_e164": "+919876522222"}
            date_str = (datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(days=1)).strftime("%Y-%m-%d")
            _, booking, _, _ = book_or_reschedule_demo(lead_id, date_str, "15:00")
            b_id = booking["id"]

            # Valid transitions
            for valid_status in ["Attended", "Not Attended", "Booked"]:
                ok, updated, err = update_existing_booking_status(b_id, valid_status)
                assert ok is True
                assert updated["booking_status"] == valid_status

            # Invalid status rejected
            ok, _, err = update_existing_booking_status(b_id, "Cancelled")
            assert ok is False
            assert "Invalid booking status" in err

    def test_confirmation_message_correctness(self, client, app, mock_supabase):
        """19. Verifies confirmation view renders student name, date, time, and Zoom placeholder URL."""
        with app.app_context():
            lead_id = "lead-conf-1"
            mock_supabase["leads"][lead_id] = {
                "id": lead_id,
                "student_name": "Meera Nambiar",
                "phone_e164": "+919876533333",
                "email": "meera@example.com",
                "class_level": "12",
                "exam_goal": "NEET",
                "interested_course": "NEET Crash Course",
            }
            demo_date = (datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(days=2)).strftime("%Y-%m-%d")
            booking_id = "book-conf-1"
            mock_supabase["bookings"][booking_id] = {
                "id": booking_id,
                "lead_id": lead_id,
                "demo_date": demo_date,
                "slot_time": "17:00",
                "booking_status": "Booked",
                "sheet_sync_status": "synced",
            }

            token = generate_booking_token(lead_id, app.config["SECRET_KEY"])
            resp = client.get(f"/booking-confirmation?token={token}&booking_id={booking_id}")

            assert resp.status_code == 200
            html = resp.data.decode("utf-8")
            assert "Meera Nambiar" in html
            assert "Demo Class Confirmed!" in html
            assert "5:00 PM IST" in html
            assert app.config["DEMO_MEETING_URL"] in html
            assert "placeholder URL configured via" in html
