"""
Supabase PostgreSQL Service Layer.
Handles persistent storage, transactional integrity, uniqueness constraints,
and relational mappings for leads and demo bookings.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from supabase import create_client, Client
from flask import current_app

logger = logging.getLogger(__name__)


class SupabaseService:
    """Service to interact with Supabase PostgreSQL."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self._url = url
        self._key = key
        self._client: Optional[Client] = None

    def _get_credentials(self) -> Tuple[str, str]:
        url = self._url or (current_app.config.get("SUPABASE_URL") if current_app else "")
        key = self._key or (current_app.config.get("SUPABASE_SECRET_KEY") if current_app else "")
        return url, key

    @property
    def client(self) -> Client:
        """Returns the initialized Supabase client, raising if not configured."""
        if self._client is None:
            url, key = self._get_credentials()
            if not url or not key:
                raise ValueError("Supabase URL and secret key must be configured in environment.")
            self._client = create_client(url, key)
        return self._client

    def is_configured(self) -> bool:
        """Checks if configuration credentials are non-empty."""
        url, key = self._get_credentials()
        return bool(url and key and "your-project" not in url)

    def check_connection(self) -> Tuple[bool, str]:
        """Performs a live connectivity test against Supabase."""
        if not self.is_configured():
            return False, "Supabase credentials are not configured."
        try:
            # Query 1 record with minimal payload to verify API and table existence
            self.client.table("leads").select("id").limit(1).execute()
            return True, "Supabase connected and reachable."
        except Exception as exc:
            logger.error("Supabase connection check failed: %s", exc)
            return False, f"Supabase connection error: {str(exc)}"

    # -------------------------------------------------------------------------
    # Lead Operations
    # -------------------------------------------------------------------------

    def find_lead_by_phone(self, phone_e164: str) -> Optional[Dict[str, Any]]:
        """Finds a single lead by its canonical E.164 phone number."""
        try:
            res = self.client.table("leads").select("*").eq("phone_e164", phone_e164).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as exc:
            logger.error("Error finding lead by phone: %s", exc)
            raise

    def get_lead_by_phone(self, phone_e164: str) -> Optional[Dict[str, Any]]:
        """Alias for find_lead_by_phone."""
        return self.find_lead_by_phone(phone_e164)

    def get_lead_by_id(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single lead by UUID."""
        try:
            res = self.client.table("leads").select("*").eq("id", str(lead_id)).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as exc:
            logger.error("Error retrieving lead by ID: %s", exc)
            raise

    def create_lead(self, lead_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Creates a new lead.
        Catches database uniqueness violations (PostgreSQL code 23505) and returns duplicate status.
        """
        try:
            payload = {
                "student_name": lead_data["student_name"].strip(),
                "phone_e164": lead_data["phone_e164"].strip(),
                "email": lead_data["email"].strip().lower(),
                "class_level": str(lead_data["class_level"]),
                "exam_goal": str(lead_data["exam_goal"]),
                "interested_course": lead_data["interested_course"].strip(),
                "sheet_sync_status": "pending",
            }
            res = self.client.table("leads").insert(payload).execute()
            if res.data and len(res.data) > 0:
                return True, res.data[0], None
            return False, None, "Database insert returned empty result."
        except Exception as exc:
            err_str = str(exc).lower()
            if "23505" in err_str or "unique constraint" in err_str or "duplicate" in err_str or "uq_leads_phone_e164" in err_str:
                logger.info("Duplicate phone number detected at database constraint level: %s", lead_data.get("phone_e164"))
                return False, None, "DUPLICATE_PHONE"
            logger.error("Database error while creating lead: %s", exc)
            return False, None, f"Database error: {str(exc)}"

    def update_lead_sheet_sync(
        self,
        lead_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Updates Google Sheets synchronization outcome for a lead."""
        try:
            payload: Dict[str, Any] = {
                "sheet_sync_status": status,
                "sheet_sync_error": error_message[:500] if error_message else None,
            }
            if status == "synced":
                payload["sheet_synced_at"] = datetime.now(timezone.utc).isoformat()
            self.client.table("leads").update(payload).eq("id", str(lead_id)).execute()
            return True
        except Exception as exc:
            logger.error("Failed to update lead sheet sync status: %s", exc)
            return False

    # -------------------------------------------------------------------------
    # Booking Operations
    # -------------------------------------------------------------------------

    def get_booking_by_lead_id(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves booking record associated with the specified lead ID."""
        try:
            res = self.client.table("bookings").select("*").eq("lead_id", str(lead_id)).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as exc:
            logger.error("Error retrieving booking for lead: %s", exc)
            raise

    def get_booking_by_id(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves booking record by its UUID."""
        try:
            res = self.client.table("bookings").select("*").eq("id", str(booking_id)).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as exc:
            logger.error("Error retrieving booking by ID: %s", exc)
            raise

    def upsert_booking(
        self,
        lead_id: str,
        demo_date: str,
        slot_time: str,
        booking_status: str = "Booked"
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Creates or reschedules a booking for a lead.
        Enforces 1 current booking per lead.
        """
        try:
            existing = self.get_booking_by_lead_id(lead_id)
            if existing:
                # Update existing booking (reschedule)
                update_payload = {
                    "demo_date": demo_date,
                    "slot_time": slot_time,
                    "booking_status": booking_status,
                    "sheet_sync_status": "pending",
                    "sheet_sync_error": None,
                }
                res = self.client.table("bookings").update(update_payload).eq("id", existing["id"]).execute()
                if res.data and len(res.data) > 0:
                    return True, res.data[0], None
                return False, None, "Reschedule update returned no records."
            else:
                # Create brand new booking
                insert_payload = {
                    "lead_id": str(lead_id),
                    "demo_date": demo_date,
                    "slot_time": slot_time,
                    "booking_status": booking_status,
                    "sheet_sync_status": "pending",
                }
                res = self.client.table("bookings").insert(insert_payload).execute()
                if res.data and len(res.data) > 0:
                    return True, res.data[0], None
                return False, None, "Booking insert returned no records."
        except Exception as exc:
            logger.error("Error upserting booking: %s", exc)
            return False, None, f"Database error: {str(exc)}"

    def update_booking_status(
        self,
        booking_id: str,
        status: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Updates booking status (Booked, Attended, Not Attended)."""
        try:
            payload = {
                "booking_status": status,
                "sheet_sync_status": "pending",
            }
            res = self.client.table("bookings").update(payload).eq("id", str(booking_id)).execute()
            if res.data and len(res.data) > 0:
                return True, res.data[0], None
            return False, None, "No booking found with given ID."
        except Exception as exc:
            logger.error("Error updating booking status: %s", exc)
            return False, None, str(exc)

    def update_booking_sheet_sync(
        self,
        booking_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Updates Google Sheets synchronization outcome for a booking."""
        try:
            payload: Dict[str, Any] = {
                "sheet_sync_status": status,
                "sheet_sync_error": error_message[:500] if error_message else None,
            }
            if status == "synced":
                payload["sheet_synced_at"] = datetime.now(timezone.utc).isoformat()
            self.client.table("bookings").update(payload).eq("id", str(booking_id)).execute()
            return True
        except Exception as exc:
            logger.error("Failed to update booking sheet sync status: %s", exc)
            return False

    # -------------------------------------------------------------------------
    # Admin & Dashboard Operations
    # -------------------------------------------------------------------------

    def list_all_leads_with_bookings(
        self,
        search_query: Optional[str] = None,
        exam_goal: Optional[str] = None,
        class_level: Optional[str] = None,
        sync_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves leads ordered by newest first, attaching each lead's booking if present.
        Supports client-side filtering for search query, exam goal, and class level.
        """
        try:
            query = self.client.table("leads").select("*").order("created_at", desc=True)
            if exam_goal:
                query = query.eq("exam_goal", exam_goal)
            if class_level:
                query = query.eq("class_level", class_level)
            if sync_status:
                query = query.eq("sheet_sync_status", sync_status)

            res = query.execute()
            leads = res.data or []

            # Fetch bookings and map by lead_id
            from app.services.settings_service import get_meeting_url_for_booking
            try:
                bookings_res = self.client.table("bookings").select("*").execute()
                bookings_map = {}
                for b in (bookings_res.data or []):
                    b["meeting_url"] = get_meeting_url_for_booking(b.get("id"))
                    bookings_map[b["lead_id"]] = b
            except Exception as b_err:
                logger.warning("Could not fetch bookings in list: %s", b_err)
                bookings_map = {}

            # Attach single booking object for ease of template rendering
            for item in leads:
                item["booking"] = bookings_map.get(item["id"])

            # In-memory filter for search string across name, phone, email
            if search_query:
                term = search_query.strip().lower()
                leads = [
                    l for l in leads
                    if term in l.get("student_name", "").lower()
                    or term in l.get("phone_e164", "").lower()
                    or term in l.get("email", "").lower()
                    or term in l.get("interested_course", "").lower()
                ]

            return leads
        except Exception as exc:
            logger.error("Error listing leads with bookings: %s", exc)
            raise

    def get_dashboard_metrics(self) -> Dict[str, int]:
        """Calculates aggregated dashboard counts."""
        try:
            leads_res = self.client.table("leads").select("id, sheet_sync_status", count="exact").execute()
            bookings_res = self.client.table("bookings").select("id, booking_status, sheet_sync_status", count="exact").execute()

            total_leads = len(leads_res.data) if leads_res.data else 0
            total_bookings = len(bookings_res.data) if bookings_res.data else 0

            attended_count = sum(1 for b in (bookings_res.data or []) if b.get("booking_status") == "Attended")
            not_attended_count = sum(1 for b in (bookings_res.data or []) if b.get("booking_status") == "Not Attended")
            booked_count = sum(1 for b in (bookings_res.data or []) if b.get("booking_status") == "Booked")

            pending_leads = sum(1 for l in (leads_res.data or []) if l.get("sheet_sync_status") in ("pending", "failed"))
            pending_bookings = sum(1 for b in (bookings_res.data or []) if b.get("sheet_sync_status") in ("pending", "failed"))

            return {
                "total_leads": total_leads,
                "total_bookings": total_bookings,
                "attended_bookings": attended_count,
                "not_attended_bookings": not_attended_count,
                "booked_bookings": booked_count,
                "pending_sync_count": pending_leads + pending_bookings,
            }
        except Exception as exc:
            logger.error("Error calculating dashboard metrics: %s", exc)
            return {
                "total_leads": 0,
                "total_bookings": 0,
                "attended_bookings": 0,
                "not_attended_bookings": 0,
                "booked_bookings": 0,
                "pending_sync_count": 0,
            }

    def get_pending_sync_items(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Retrieves leads and bookings requiring synchronization."""
        try:
            leads = self.client.table("leads").select("*").in_("sheet_sync_status", ["pending", "failed"]).execute().data or []
            bookings = self.client.table("bookings").select("*, leads(student_name)").in_("sheet_sync_status", ["pending", "failed"]).execute().data or []
            return leads, bookings
        except Exception as exc:
            logger.error("Error retrieving pending sync records: %s", exc)
            return [], []


# Global service instance
supabase_service = SupabaseService()
