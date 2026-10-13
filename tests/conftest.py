"""
Pytest Fixtures and Mock Environment for KMIE Automation Suite.
Provides isolated Flask application test client with mocked database and spreadsheet layers.
"""
import pytest
from unittest.mock import MagicMock
from app import create_app
from app.services.supabase_service import supabase_service
from app.services.google_sheets_service import google_sheets_service


@pytest.fixture
def app():
    """Creates a test Flask application context."""
    test_app = create_app("testing")
    yield test_app


@pytest.fixture
def client(app):
    """Provides an unauthenticated Flask test client."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Provides an authenticated administrator test client."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_user"] = "testadmin"
    return client


@pytest.fixture
def mock_supabase(monkeypatch):
    """
    Mock Supabase database layer simulating in-memory storage,
    unique phone constraint violations, and relationship lookups.
    """
    mock_leads_db = {}
    mock_bookings_db = {}

    def fake_find_by_phone(phone_e164):
        for lead in mock_leads_db.values():
            if lead["phone_e164"] == phone_e164:
                return lead
        return None

    def fake_get_lead_by_id(lead_id):
        return mock_leads_db.get(str(lead_id))

    def fake_create_lead(lead_data):
        # Simulate PostgreSQL unique constraint
        phone = lead_data["phone_e164"]
        if fake_find_by_phone(phone):
            return False, None, "DUPLICATE_PHONE"

        new_id = f"lead-uuid-{len(mock_leads_db) + 1}"
        record = {
            "id": new_id,
            "student_name": lead_data["student_name"],
            "phone_e164": phone,
            "email": lead_data["email"],
            "class_level": lead_data["class_level"],
            "exam_goal": lead_data["exam_goal"],
            "interested_course": lead_data["interested_course"],
            "sheet_sync_status": "pending",
            "sheet_synced_at": None,
            "sheet_sync_error": None,
            "created_at": "2026-10-13T10:00:00Z",
            "updated_at": "2026-10-13T10:00:00Z",
        }
        mock_leads_db[new_id] = record
        return True, record, None

    def fake_update_lead_sheet_sync(lead_id, status, error=None):
        if str(lead_id) in mock_leads_db:
            mock_leads_db[str(lead_id)]["sheet_sync_status"] = status
            mock_leads_db[str(lead_id)]["sheet_sync_error"] = error
            return True
        return False

    def fake_get_booking_by_lead_id(lead_id):
        for b in mock_bookings_db.values():
            if b["lead_id"] == str(lead_id):
                return b
        return None

    def fake_get_booking_by_id(booking_id):
        return mock_bookings_db.get(str(booking_id))

    def fake_upsert_booking(lead_id, demo_date, slot_time, booking_status="Booked"):
        existing = fake_get_booking_by_lead_id(lead_id)
        if existing:
            existing["demo_date"] = demo_date
            existing["slot_time"] = slot_time
            existing["booking_status"] = booking_status
            existing["sheet_sync_status"] = "pending"
            return True, existing, None

        b_id = f"book-uuid-{len(mock_bookings_db) + 1}"
        new_booking = {
            "id": b_id,
            "lead_id": str(lead_id),
            "demo_date": demo_date,
            "slot_time": slot_time,
            "booking_status": booking_status,
            "sheet_sync_status": "pending",
            "created_at": "2026-10-13T10:05:00Z",
            "updated_at": "2026-10-13T10:05:00Z",
        }
        mock_bookings_db[b_id] = new_booking
        return True, new_booking, None

    def fake_update_booking_status(booking_id, status):
        if str(booking_id) in mock_bookings_db:
            mock_bookings_db[str(booking_id)]["booking_status"] = status
            mock_bookings_db[str(booking_id)]["sheet_sync_status"] = "pending"
            return True, mock_bookings_db[str(booking_id)], None
        return False, None, "Booking not found"

    def fake_update_booking_sheet_sync(booking_id, status, error=None):
        if str(booking_id) in mock_bookings_db:
            mock_bookings_db[str(booking_id)]["sheet_sync_status"] = status
            mock_bookings_db[str(booking_id)]["sheet_sync_error"] = error
            return True
        return False

    def fake_list_all_leads_with_bookings(*args, **kwargs):
        res = []
        for lead in mock_leads_db.values():
            lead_copy = dict(lead)
            lead_copy["booking"] = fake_get_booking_by_lead_id(lead["id"])
            res.append(lead_copy)
        return res

    def fake_get_dashboard_metrics():
        return {
            "total_leads": len(mock_leads_db),
            "total_bookings": len(mock_bookings_db),
            "attended_bookings": sum(1 for b in mock_bookings_db.values() if b["booking_status"] == "Attended"),
            "not_attended_bookings": sum(1 for b in mock_bookings_db.values() if b["booking_status"] == "Not Attended"),
            "booked_bookings": sum(1 for b in mock_bookings_db.values() if b["booking_status"] == "Booked"),
            "pending_sync_count": 0,
        }

    monkeypatch.setattr(supabase_service, "find_lead_by_phone", fake_find_by_phone)
    monkeypatch.setattr(supabase_service, "get_lead_by_id", fake_get_lead_by_id)
    monkeypatch.setattr(supabase_service, "create_lead", fake_create_lead)
    monkeypatch.setattr(supabase_service, "update_lead_sheet_sync", fake_update_lead_sheet_sync)
    monkeypatch.setattr(supabase_service, "get_booking_by_lead_id", fake_get_booking_by_lead_id)
    monkeypatch.setattr(supabase_service, "get_booking_by_id", fake_get_booking_by_id)
    monkeypatch.setattr(supabase_service, "upsert_booking", fake_upsert_booking)
    monkeypatch.setattr(supabase_service, "update_booking_status", fake_update_booking_status)
    monkeypatch.setattr(supabase_service, "update_booking_sheet_sync", fake_update_booking_sheet_sync)
    monkeypatch.setattr(supabase_service, "list_all_leads_with_bookings", fake_list_all_leads_with_bookings)
    monkeypatch.setattr(supabase_service, "get_dashboard_metrics", fake_get_dashboard_metrics)

    return {
        "leads": mock_leads_db,
        "bookings": mock_bookings_db,
    }


@pytest.fixture
def mock_sheets(monkeypatch):
    """
    Mock Google Sheets service tracking calls and simulating success/failure.
    """
    calls = {
        "synced_leads": [],
        "synced_bookings": [],
        "should_fail": False,
        "error_message": "Simulated Google Sheets API timeout",
    }

    def fake_sync_lead(lead):
        if calls["should_fail"]:
            return False, calls["error_message"]
        # Idempotency check: don't duplicate
        lead_id = lead["id"]
        if lead_id not in [l["id"] for l in calls["synced_leads"]]:
            calls["synced_leads"].append(lead)
        return True, "Enquiry successfully synchronized."

    def fake_sync_booking(booking, student_name):
        if calls["should_fail"]:
            return False, calls["error_message"]
        # If exists, update
        existing = next((b for b in calls["synced_bookings"] if b["id"] == booking["id"]), None)
        if existing:
            existing.update(booking)
            existing["student_name"] = student_name
        else:
            b_copy = dict(booking)
            b_copy["student_name"] = student_name
            calls["synced_bookings"].append(b_copy)
        return True, "Booking synchronized."

    monkeypatch.setattr(google_sheets_service, "is_configured", lambda: True)
    monkeypatch.setattr(google_sheets_service, "sync_lead", fake_sync_lead)
    monkeypatch.setattr(google_sheets_service, "sync_booking", fake_sync_booking)

    return calls
