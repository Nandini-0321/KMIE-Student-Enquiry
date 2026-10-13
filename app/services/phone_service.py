"""
Phone Number Validation and Canonical E.164 Normalization Service.
Implements India (IN) default parsing and handles common formatting differences.
"""
import re
from typing import Tuple
import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


def normalize_phone_number(raw_phone: str, default_region: str = "IN") -> Tuple[bool, str, str]:
    """
    Validates and normalizes phone numbers into canonical E.164 format.

    Supports:
    - 10-digit Indian numbers: 9876543210
    - Formatted Indian numbers: +91 98765 43210, +91-98765-43210, (98765) 43210
    - Leading 00 international prefix: 0091 98765 43210, 001 202 555 0101
    - International numbers with country code: +1 202-555-0101, +44 20 7946 0919

    Returns:
        (is_valid: bool, canonical_e164_or_error: str, international_display: str)
    """
    if not raw_phone or not isinstance(raw_phone, str):
        return False, "Phone number is required.", ""

    cleaned = raw_phone.strip()
    if not cleaned:
        return False, "Phone number cannot be blank.", ""

    # Replace leading 00 with '+' for standard international dialing
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:].strip()

    # Reject multiple plus signs or plus signs not at the start
    if cleaned.count("+") > 1 or ("+" in cleaned and not cleaned.startswith("+")):
        return False, "Phone number contains invalid plus symbol placement.", ""

    # Reject obviously invalid or malicious strings
    # Numbers should only contain digits, plus, hyphens, spaces, and parentheses
    if not re.match(r"^[\+0-9\s\-\(\)\.]+$", cleaned):
        return False, "Phone number contains invalid characters.", ""

    # Filter out strings with too few digits
    digits_only = re.sub(r"\D", "", cleaned)
    if len(digits_only) < 7:
        return False, "Phone number is too short.", ""
    if len(digits_only) > 15:
        return False, "Phone number is too long.", ""

    try:
        parsed = phonenumbers.parse(cleaned, default_region)
    except NumberParseException as err:
        return False, f"Invalid phone number format: {err._msg}", ""
    except Exception:
        return False, "Could not parse phone number.", ""

    # Validate against libphonenumber metadata
    if not phonenumbers.is_valid_number(parsed):
        # Edge case check for possible numbers (e.g. testing ranges)
        if not phonenumbers.is_possible_number(parsed):
            return False, "Please enter a valid active phone number.", ""

    e164_formatted = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    intl_formatted = phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)

    return True, e164_formatted, intl_formatted


def mask_phone_number(e164_phone: str) -> str:
    """
    Safely masks a phone number for logging or safe display.
    Example: +919876543210 -> +91 98*** ***10
    """
    if not e164_phone or len(e164_phone) < 6:
        return "***"
    prefix = e164_phone[:5]
    suffix = e164_phone[-2:]
    return f"{prefix}*****{suffix}"
