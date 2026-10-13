"""
Tests for Student Enquiry Submission, Validation, and Duplicate Prevention.
Verifies Requirements:
- 1. Valid enquiry creation
- 2. Required-field validation
- 3. Invalid email rejection
- 7. Duplicate lead rejection
- 8. Database uniqueness error handling
"""
import pytest
from app.services.enquiry_service import process_student_enquiry, validate_enquiry_payload


class TestStudentEnquiries:
    """Test suite for enquiry workflows."""

    def test_valid_enquiry_creation(self, app, mock_supabase, mock_sheets):
        """1. Verifies that a valid enquiry is created and persisted."""
        with app.app_context():
            payload = {
                "student_name": "Rohan Verma",
                "phone_number": "+91 98765 43210",
                "email": "rohan.verma@example.com",
                "class_level": "11",
                "exam_goal": "NEET",
                "interested_course": "NEET Long-Term Preparation",
            }
            success, is_duplicate, lead, token, msg = process_student_enquiry(payload)

            assert success is True
            assert is_duplicate is False
            assert lead is not None
            assert lead["student_name"] == "Rohan Verma"
            assert lead["phone_e164"] == "+919876543210"
            assert token is not None

    def test_required_field_validation(self, app):
        """2. Verifies that missing required fields trigger validation errors."""
        with app.app_context():
            # Missing student name
            ok, err, _ = validate_enquiry_payload({
                "student_name": "",
                "phone_number": "9876543210",
                "email": "test@example.com",
                "class_level": "11",
                "exam_goal": "NEET",
                "interested_course": "NEET Long-Term Preparation",
            })
            assert ok is False
            assert "Student Name is required" in err

            # Invalid class level
            ok, err, _ = validate_enquiry_payload({
                "student_name": "Pooja",
                "phone_number": "9876543210",
                "email": "pooja@example.com",
                "class_level": "10",  # Only 11 or 12 allowed
                "exam_goal": "NEET",
                "interested_course": "NEET Long-Term Preparation",
            })
            assert ok is False
            assert "Class must be one of" in err

            # Invalid exam goal
            ok, err, _ = validate_enquiry_payload({
                "student_name": "Pooja",
                "phone_number": "9876543210",
                "email": "pooja@example.com",
                "class_level": "12",
                "exam_goal": "UPSC",  # Only NEET or JEE allowed
                "interested_course": "NEET Long-Term Preparation",
            })
            assert ok is False
            assert "Exam goal must be one of" in err

    def test_invalid_email_rejection(self, app):
        """3. Verifies that invalid or malformed email addresses are rejected."""
        with app.app_context():
            bad_emails = [
                "plainaddress",
                "@missingusername.com",
                "username@.com",
                "user name@domain.com",
            ]
            for bad_email in bad_emails:
                ok, err, _ = validate_enquiry_payload({
                    "student_name": "Vikram",
                    "phone_number": "9876543210",
                    "email": bad_email,
                    "class_level": "12",
                    "exam_goal": "JEE",
                    "interested_course": "JEE Advanced Preparation",
                })
                assert ok is False
                assert "Invalid email address" in err

    def test_duplicate_lead_rejection_different_phone_format(self, app, mock_supabase, mock_sheets):
        """
        7. Verifies that submitting an existing phone in a different formatting
        detects the duplicate, rejects a second lead, and provides a duplicate notice.
        """
        with app.app_context():
            # First submission (standard 10-digit)
            p1 = {
                "student_name": "Ananya Sharma",
                "phone_number": "9876511223",
                "email": "ananya.first@example.com",
                "class_level": "11",
                "exam_goal": "NEET",
                "interested_course": "NEET Long-Term Preparation",
            }
            s1, dup1, lead1, token1, _ = process_student_enquiry(p1)
            assert s1 is True
            assert dup1 is False

            # Second submission using +91, spaces, and hyphens for the same number
            p2 = {
                "student_name": "Ananya Sharma Duplicate",
                "phone_number": "+91 98765-11223",
                "email": "ananya.second@example.com",
                "class_level": "11",
                "exam_goal": "NEET",
                "interested_course": "NEET Crash Course",
            }
            s2, dup2, lead2, token2, msg2 = process_student_enquiry(p2)

            assert s2 is False
            assert dup2 is True
            assert "already been registered" in msg2
            # Verify only 1 lead exists in database
            assert len(mock_supabase["leads"]) == 1

    def test_database_uniqueness_race_condition_handling(self, app, monkeypatch, mock_supabase):
        """
        8. Verifies that database uniqueness error (code 23505) is caught gracefully
        if two simultaneous requests arrive.
        """
        with app.app_context():
            # Pre-populate lead directly in mock DB
            mock_supabase["leads"]["lead-1"] = {
                "id": "lead-1",
                "student_name": "Concurrent User",
                "phone_e164": "+919876500000",
                "email": "concurrent@example.com",
                "class_level": "12",
                "exam_goal": "JEE",
                "interested_course": "JEE Main Preparation",
                "sheet_sync_status": "synced",
            }

            # Simulate pre-check passing (returning None) but create_lead failing with duplicate error
            from app.services.supabase_service import supabase_service
            monkeypatch.setattr(supabase_service, "find_lead_by_phone", lambda p: mock_supabase["leads"]["lead-1"])
            monkeypatch.setattr(supabase_service, "create_lead", lambda data: (False, None, "DUPLICATE_PHONE"))

            payload = {
                "student_name": "Concurrent User 2",
                "phone_number": "9876500000",
                "email": "concurrent2@example.com",
                "class_level": "12",
                "exam_goal": "JEE",
                "interested_course": "JEE Main Preparation",
            }
            success, is_dup, lead, token, msg = process_student_enquiry(payload)

            assert success is False
            assert is_dup is True
            assert "already been registered" in msg

    def test_honeypot_spam_rejection(self, app):
        """Verifies that automated bots filling the honeypot field are rejected."""
        with app.app_context():
            ok, err, _ = validate_enquiry_payload({
                "student_name": "Bot Name",
                "phone_number": "9876543210",
                "email": "bot@example.com",
                "class_level": "11",
                "exam_goal": "NEET",
                "interested_course": "Foundation Course",
                "website_url_check": "http://spam-link.com",  # Honeypot filled
            })
            assert ok is False
            assert "Automated submission rejected" in err
