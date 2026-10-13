"""
Authentication, Session Management, and Signed Token Security Service.
"""
import functools
import hmac
from typing import Optional, Tuple
from flask import session, redirect, url_for, flash, request, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature


def hash_password(plain_password: str) -> str:
    """Generates a secure password hash."""
    return generate_password_hash(plain_password, method="scrypt")


def verify_admin_password(
    username: str,
    password: str,
    expected_username: str,
    expected_hash: str
) -> bool:
    """
    Safely verifies admin credentials.
    Uses constant time comparison for username and secure hash check.
    """
    if not username or not password or not expected_username or not expected_hash:
        return False

    username_matches = hmac.compare_digest(username.strip(), expected_username.strip())
    if not username_matches:
        return False

    return check_password_hash(expected_hash, password)


def login_admin(username: str) -> None:
    """Sets session attributes on successful admin login."""
    session.clear()
    session["is_admin"] = True
    session["admin_user"] = username


def logout_admin() -> None:
    """Clears admin session."""
    session.clear()


def is_admin_logged_in() -> bool:
    """Checks whether the current session is an authenticated admin."""
    return session.get("is_admin") is True and bool(session.get("admin_user"))


def admin_required(view_func):
    """Decorator to protect administration routes."""
    @functools.wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not is_admin_logged_in():
            flash("Administrator login is required to access this page.", "warning")
            return redirect(url_for("admin.login", next=request.path))
        return view_func(*args, **kwargs)
    return decorated_view


def generate_booking_token(lead_id: str, secret_key: str) -> str:
    """
    Generates a cryptographically signed, URL-safe token containing the lead ID.
    Prevents unauthorized or forged booking requests.
    """
    serializer = URLSafeTimedSerializer(secret_key, salt="kmie-booking-token-salt")
    return serializer.dumps({"lead_id": str(lead_id)})


def verify_booking_token(
    token: str,
    secret_key: str,
    max_age_seconds: int = 7200
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verifies the signed booking token and extracts the lead ID.

    Returns:
        (is_valid: bool, lead_id: Optional[str], error_message: Optional[str])
    """
    if not token:
        return False, None, "Booking session token is missing."

    serializer = URLSafeTimedSerializer(secret_key, salt="kmie-booking-token-salt")
    try:
        data = serializer.loads(token, max_age=max_age_seconds)
        lead_id = data.get("lead_id")
        if not lead_id:
            return False, None, "Invalid booking token contents."
        return True, lead_id, None
    except SignatureExpired:
        return False, None, "Your booking link has expired. Please submit a new enquiry or contact support."
    except BadSignature:
        return False, None, "Invalid or tampered booking token."
    except Exception as exc:
        return False, None, f"Could not verify booking token: {str(exc)}"
