"""
Application Configuration Module for KMIE Student Enquiry & Demo Booking System.
Handles environment-based settings with sensible defaults for development.
"""
import os
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


class Config:
    """Base Configuration."""
    APP_ENV = os.getenv("APP_ENV", "development")
    SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-insecure-secret-key-change-in-production")
    
    # Session and Cookie Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Enabled in Production
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 7200  # 2 hours
    
    # Timezone
    TIMEZONE = os.getenv("TZ", "Asia/Kolkata")
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_SECRET_KEY = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
    
    # Google Sheets Integration
    GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
    GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64", "").strip()
    GOOGLE_SERVICE_ACCOUNT_FILE_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE_PATH", "").strip()
    
    # Admin Credentials
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
    
    # Demo Booking Configuration
    DEMO_MEETING_URL = os.getenv("DEMO_MEETING_URL", "https://zoom.us/j/placeholder-kmie-demo-session")
    BOOKING_TOKEN_MAX_AGE_SECONDS = int(os.getenv("BOOKING_TOKEN_MAX_AGE_SECONDS", "7200"))
    
    # Business Rules & Configurable Choices
    COURSE_OPTIONS: List[str] = [
        "NEET Long-Term Preparation",
        "NEET Crash Course",
        "JEE Main Preparation",
        "JEE Advanced Preparation",
        "Foundation Course",
        "Other",
    ]
    
    ALLOWED_CLASSES: List[str] = ["11", "12"]
    ALLOWED_EXAM_GOALS: List[str] = ["NEET", "JEE"]
    
    ALLOWED_SLOT_TIMES: List[str] = ["13:00", "15:00", "17:00", "19:00"]
    SLOT_TIME_LABELS: Dict[str, str] = {
        "13:00": "1:00 PM IST",
        "15:00": "3:00 PM IST",
        "17:00": "5:00 PM IST",
        "19:00": "7:00 PM IST",
    }
    
    BOOKING_STATUSES: List[str] = ["Booked", "Attended", "Not Attended"]


class DevelopmentConfig(Config):
    """Development Configuration."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production Configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing Configuration."""
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False  # Disable CSRF in tests for direct post requests unless explicitly tested
    SECRET_KEY = "test-secret-key-for-unit-tests"
    ADMIN_USERNAME = "testadmin"
    # Pre-hashed 'testpassword123'
    ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$u4t8W51Z0p98$f59a35e4fc416c117187c9339e0839e26a798a760b938f3cbffbfbbdf9e28bfb51fa1616ffb56bbef2662fa9c6fa3ee9713c8297b4ad85c7f8a7983637e6daef"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
