"""
Tests for Phone Number Normalization, Validation, and Format Equivalence.
Verifies Requirements:
- 4. Invalid phone rejection
- 5. Indian national and international country code normalization
- 6. Phone format equivalence
"""
import pytest
from app.services.phone_service import normalize_phone_number, mask_phone_number


class TestPhoneNormalization:
    """Test suite for telephone number canonicalization."""

    def test_indian_phone_format_equivalence(self):
        """
        Verifies that multiple Indian representations of the same phone number
        resolve to the exact same canonical E.164 string (+919876543210).
        """
        variants = [
            "9876543210",
            "+91 98765 43210",
            "+91-98765-43210",
            "0091 98765 43210",
            "+91 (98765) 43210",
            "+919876543210",
        ]
        canonical_target = "+919876543210"

        for variant in variants:
            is_valid, canonical, intl = normalize_phone_number(variant)
            assert is_valid is True, f"Failed for variant: {variant}"
            assert canonical == canonical_target, f"Expected {canonical_target}, got {canonical} for {variant}"

    def test_international_number_normalization(self):
        """
        Verifies that valid international numbers with country codes normalize correctly.
        """
        test_cases = [
            ("+1 202-555-0101", "+12025550101"),
            ("+1 (202) 555-0102", "+12025550102"),
            ("001 202 555 0103", "+12025550103"),
            ("+44 20 7946 0919", "+442079460919"),
        ]

        for raw_input, expected_e164 in test_cases:
            is_valid, canonical, _ = normalize_phone_number(raw_input)
            assert is_valid is True, f"Failed for international input: {raw_input}"
            assert canonical == expected_e164

    def test_invalid_phone_rejections(self):
        """
        Verifies that malformed, non-numeric, or incomplete inputs are rejected.
        """
        invalid_inputs = [
            "",
            "   ",
            "abcdefghij",
            "12345",  # Too short
            "98765432109876543210",  # Too long
            "++919876543210",
            "98765@43210",
        ]

        for invalid in invalid_inputs:
            is_valid, err_msg, _ = normalize_phone_number(invalid)
            assert is_valid is False, f"Expected rejection for: {invalid}"
            assert len(err_msg) > 0

    def test_phone_masking(self):
        """
        Verifies that phone numbers are safely masked for display.
        """
        masked = mask_phone_number("+919876543210")
        assert masked == "+9198*****10"
        assert mask_phone_number("") == "***"
