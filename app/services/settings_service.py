"""
Settings Service for KMIE Application.
Manages global and per-booking demo class links with persistent JSON storage.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
from flask import current_app

logger = logging.getLogger(__name__)

SETTINGS_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SETTINGS_FILE = SETTINGS_DIR / "app_settings.json"


def _ensure_settings_dir():
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> Dict[str, Any]:
    """Loads application settings from disk."""
    _ensure_settings_dir()
    if not SETTINGS_FILE.exists():
        default_url = (
            current_app.config.get("DEMO_MEETING_URL")
            if current_app
            else os.getenv("DEMO_MEETING_URL", "https://zoom.us/j/placeholder-kmie-demo-session")
        )
        defaults = {
            "demo_meeting_url": default_url,
            "booking_links": {},
        }
        save_settings(defaults)
        return defaults

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Error reading settings file: %s", exc)
        return {}


def save_settings(settings: Dict[str, Any]) -> bool:
    """Saves application settings to disk."""
    _ensure_settings_dir()
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as exc:
        logger.error("Error saving settings file: %s", exc)
        return False


def get_global_meeting_url() -> str:
    """Retrieves the active global demo meeting URL."""
    settings = load_settings()
    configured = settings.get("demo_meeting_url")
    if configured:
        return configured.strip()
    return (
        current_app.config.get("DEMO_MEETING_URL")
        if current_app
        else os.getenv("DEMO_MEETING_URL", "https://zoom.us/j/placeholder-kmie-demo-session")
    )


def update_global_meeting_url(new_url: str) -> bool:
    """Updates the global demo meeting URL configured by the administrator."""
    settings = load_settings()
    settings["demo_meeting_url"] = new_url.strip()
    return save_settings(settings)


def get_meeting_url_for_booking(booking_id: Optional[str]) -> str:
    """Retrieves specific meeting link for a booking, or falls back to global link."""
    if booking_id:
        settings = load_settings()
        booking_links = settings.get("booking_links", {})
        if str(booking_id) in booking_links and booking_links[str(booking_id)]:
            return booking_links[str(booking_id)].strip()
    return get_global_meeting_url()


def set_meeting_url_for_booking(booking_id: str, url: str) -> bool:
    """Stores a custom meeting link for a specific booking."""
    if not booking_id:
        return False
    settings = load_settings()
    if "booking_links" not in settings:
        settings["booking_links"] = {}
    settings["booking_links"][str(booking_id)] = url.strip()
    return save_settings(settings)
