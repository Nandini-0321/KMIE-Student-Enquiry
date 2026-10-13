"""
Tests for Admin Demo Class Meeting Link Management, Dashboard Booking Status Updates,
and Student Meeting Link Visibility upon Slot Reservation / Status Check.
"""
import pytest
from unittest.mock import MagicMock
from app.services.supabase_service import supabase_service
from app.services.settings_service import get_global_meeting_url, update_global_meeting_url, get_meeting_url_for_booking


class TestMeetingLinksAndDashboard:
    """Test suite for meeting link settings and booking status controls."""

    def test_admin_update_global_meeting_url(self, auth_client):
        """Verifies admin can update the global demo class meeting link."""
        orig_url = get_global_meeting_url()
        try:
            new_url = "https://zoom.us/j/999888777?pwd=testkmiedemo"
            resp = auth_client.post(
                "/admin/settings/meeting-url",
                data={"meeting_url": new_url},
                follow_redirects=True
            )
            assert resp.status_code == 200
            assert get_global_meeting_url() == new_url
        finally:
            update_global_meeting_url(orig_url)

    def test_admin_dashboard_renders_meeting_config_and_booking_details(self, auth_client, monkeypatch):
        """Verifies admin dashboard displays meeting configuration card and booking details."""
        fake_lead = {
            "id": "lead-111",
            "student_name": "Priya Sharma",
            "phone_e164": "+919876543210",
            "email": "priya.sharma@example.com",
            "class_level": "11",
            "exam_goal": "NEET",
            "interested_course": "NEET 1-Year Intensive Course",
            "sheet_sync_status": "synced",
            "booking": {
                "id": "book-111",
                "lead_id": "lead-111",
                "demo_date": "2026-10-14",
                "slot_time": "13:00",
                "booking_status": "Booked",
                "sheet_sync_status": "synced",
                "meeting_url": "https://zoom.us/j/placeholder-kmie-demo-session",
            }
        }

        monkeypatch.setattr(supabase_service, "list_all_leads_with_bookings", lambda **kw: [fake_lead])
        monkeypatch.setattr(supabase_service, "get_dashboard_metrics", lambda: {
            "total_leads": 1,
            "total_bookings": 1,
            "attended_bookings": 0,
            "not_attended_bookings": 0,
            "booked_bookings": 1,
            "pending_sync_count": 0,
        })

        resp = auth_client.get("/admin/dashboard")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")

        # Verify meeting URL configuration card is present
        assert "Demo Class Meeting URL Configuration" in html
        assert "id=\"global-meeting-url-input\"" in html
        assert "Save Meeting Link" in html

        # Verify Demo Appointment and Booking Status are displayed for the lead
        assert "Priya Sharma" in html
        assert "2026-10-14" in html
        assert "1:00 PM" in html or "13:00" in html
        assert "Meeting Link" in html
        assert "name=\"status\"" in html
        assert "Booked" in html
        assert "Attended" in html

    def test_admin_change_booking_status(self, auth_client, monkeypatch):
        """Verifies changing booking status dropdown from Booked to Attended."""
        mock_update = MagicMock(return_value=(True, {"id": "book-111", "booking_status": "Attended"}, None))
        monkeypatch.setattr("app.routes.admin.update_existing_booking_status", mock_update)

        resp = auth_client.post(
            "/admin/bookings/book-111/status",
            data={"status": "Attended"},
            follow_redirects=True
        )
        assert resp.status_code == 200
        mock_update.assert_called_once_with("book-111", "Attended")

    def test_student_check_status_displays_meeting_link(self, client, monkeypatch):
        """Verifies a student checking status with their phone sees their booking details and meeting link."""
        fake_lead = {
            "id": "lead-222",
            "student_name": "Washim Shaikh",
            "phone_e164": "+918884958185",
            "email": "washim@example.com",
            "class_level": "12",
            "exam_goal": "JEE",
            "interested_course": "JEE Advanced Masterclass",
            "sheet_sync_status": "synced",
        }
        fake_booking = {
            "id": "book-222",
            "lead_id": "lead-222",
            "demo_date": "2026-10-15",
            "slot_time": "15:00",
            "booking_status": "Booked",
            "sheet_sync_status": "synced",
        }

        monkeypatch.setattr(supabase_service, "get_lead_by_phone", lambda phone: fake_lead)
        monkeypatch.setattr(supabase_service, "get_booking_by_lead_id", lambda lead_id: fake_booking)

        resp = client.post(
            "/check-status",
            data={"phone_number": "8884958185"},
            follow_redirects=True
        )
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")

        assert "Washim Shaikh" in html
        assert "Confirmed Demo Appointment" in html
        assert "2026-10-15" in html or "October" in html
        assert "Live Demo Class Meeting Link" in html
        assert "Join Meeting" in html

    def test_booking_slot_page_displays_active_meeting_link_when_rescheduling(self, app, client, monkeypatch):
        """Verifies /book-demo displays the current meeting link if student already has a slot."""
        from app.services.auth_service import generate_booking_token

        token = generate_booking_token("lead-333", app.config["SECRET_KEY"])
        fake_lead = {
            "id": "lead-333",
            "student_name": "Ananya Iyer",
            "phone_e164": "+919988776655",
            "email": "ananya@example.com",
            "class_level": "11",
            "exam_goal": "NEET",
            "interested_course": "NEET 2-Year Foundation",
        }
        fake_booking = {
            "id": "book-333",
            "lead_id": "lead-333",
            "demo_date": "2026-10-16",
            "slot_time": "17:00",
            "booking_status": "Booked",
        }

        monkeypatch.setattr(supabase_service, "get_lead_by_id", lambda lead_id: fake_lead)
        monkeypatch.setattr(supabase_service, "get_booking_by_lead_id", lambda lead_id: fake_booking)

        resp = client.get(f"/book-demo?token={token}")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")

        assert "Current Booking Active" in html
        assert "Your Active Demo Session Link" in html
        assert "id=\"active-booking-meeting-url\"" in html
        assert "Join Meeting" in html
