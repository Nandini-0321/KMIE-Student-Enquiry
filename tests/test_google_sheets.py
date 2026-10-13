"""
Tests for Google Sheets API Integration, Failure Resilience, and Idempotent Retries.
Verifies Requirements:
- 9. Successful Google Sheets synchronization
- 10. Google Sheets failure handling
- 11. Retry without duplicate spreadsheet rows
"""
import pytest
from app.services.enquiry_service import process_student_enquiry
from app.services.booking_service import book_or_reschedule_demo
from app.services.google_sheets_service import GoogleSheetsService


class TestGoogleSheetsIntegration:
    """Test suite for spreadsheet synchronization."""

    def test_successful_google_sheets_sync(self, app, mock_supabase, mock_sheets):
        """9. Verifies that valid enquiry triggers Google Sheets sync and marks status 'synced'."""
        with app.app_context():
            payload = {
                "student_name": "Sheet Test User",
                "phone_number": "+91 98765 77777",
                "email": "sheet.test@example.com",
                "class_level": "11",
                "exam_goal": "JEE",
                "interested_course": "JEE Main Preparation",
            }
            success, _, lead, _, _ = process_student_enquiry(payload)

            assert success is True
            assert lead["sheet_sync_status"] == "synced"
            assert len(mock_sheets["synced_leads"]) == 1
            assert mock_sheets["synced_leads"][0]["id"] == lead["id"]

    def test_google_sheets_failure_handling(self, app, mock_supabase, mock_sheets):
        """
        10. Verifies that when Google Sheets fails:
        - The enquiry is still saved in Supabase
        - Sync status is marked as 'failed' with error recorded
        - The operation does not crash or falsely claim the enquiry failed.
        """
        with app.app_context():
            mock_sheets["should_fail"] = True
            mock_sheets["error_message"] = "Google Sheets API quota exceeded"

            payload = {
                "student_name": "Failure Resilience User",
                "phone_number": "+91 98765 88888",
                "email": "fail.test@example.com",
                "class_level": "12",
                "exam_goal": "NEET",
                "interested_course": "NEET Crash Course",
            }
            success, is_dup, lead, token, msg = process_student_enquiry(payload)

            # Database persistence MUST still succeed
            assert success is True
            assert is_dup is False
            assert lead is not None
            assert lead["sheet_sync_status"] == "failed"
            assert "quota exceeded" in lead["sheet_sync_error"]
            # Verify record remains safely saved in mock database
            assert lead["id"] in mock_supabase["leads"]

    def test_retry_without_duplicate_rows(self, app, mock_supabase, mock_sheets):
        """
        11. Verifies that retrying synchronization on an already-synced record
        does not append duplicate rows to the spreadsheet.
        """
        with app.app_context():
            lead_record = {
                "id": "lead-retry-123",
                "student_name": "Retry User",
                "phone_e164": "+919876599900",
                "email": "retry@example.com",
                "class_level": "11",
                "exam_goal": "NEET",
                "interested_course": "Foundation Course",
                "created_at": "2026-10-13T10:00:00Z",
            }

            # First sync attempt
            from app.services.google_sheets_service import google_sheets_service
            s1, msg1 = google_sheets_service.sync_lead(lead_record)
            assert s1 is True
            assert len(mock_sheets["synced_leads"]) == 1

            # Second sync attempt (retry)
            s2, msg2 = google_sheets_service.sync_lead(lead_record)
            assert s2 is True
            # Row count in spreadsheet must remain 1
            assert len(mock_sheets["synced_leads"]) == 1

    def test_booking_status_sheet_sync_updates_row(self, app, mock_supabase, mock_sheets):
        """
        Verifies that synchronizing a rescheduled booking updates the row rather than appending a new one.
        """
        with app.app_context():
            from app.services.google_sheets_service import google_sheets_service
            booking_record = {
                "id": "book-sync-1",
                "lead_id": "lead-sync-1",
                "demo_date": "2026-10-20",
                "slot_time": "13:00",
                "booking_status": "Booked",
                "created_at": "2026-10-13T10:00:00Z",
            }

            # Initial sync
            google_sheets_service.sync_booking(booking_record, "Test Student")
            assert len(mock_sheets["synced_bookings"]) == 1
            assert mock_sheets["synced_bookings"][0]["booking_status"] == "Booked"

            # Reschedule and update status to Attended
            booking_record["booking_status"] = "Attended"
            booking_record["slot_time"] = "17:00"
            google_sheets_service.sync_booking(booking_record, "Test Student")

            assert len(mock_sheets["synced_bookings"]) == 1
            assert mock_sheets["synced_bookings"][0]["booking_status"] == "Attended"
            assert mock_sheets["synced_bookings"][0]["slot_time"] == "17:00"
