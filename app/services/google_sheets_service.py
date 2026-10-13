"""
Google Sheets Synchronization Service.
Handles service-account authentication, tab initialization, idempotent sync,
and bounded retries for Enquiries and Demo Bookings.
"""
import base64
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import pytz
from flask import current_app
from google.oauth2.service_account import Credentials
import gspread
from gspread.exceptions import WorksheetNotFound, APIError, SpreadsheetNotFound

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

TAB_ENQUIRIES = "Enquiries"
HEADERS_ENQUIRIES = [
    "Lead ID",
    "Submission Timestamp",
    "Student Name",
    "Normalized Phone Number",
    "Email",
    "Class",
    "Exam Goal",
    "Interested Course",
]

TAB_BOOKINGS = "Demo Bookings"
HEADERS_BOOKINGS = [
    "Booking ID",
    "Lead ID",
    "Student Name",
    "Demo Date",
    "Demo Time",
    "Booking Status",
    "Last Updated",
]


class GoogleSheetsService:
    """Manages idempotent synchronization with Google Sheets."""

    def __init__(
        self,
        sheet_id: Optional[str] = None,
        service_account_b64: Optional[str] = None,
        service_account_file: Optional[str] = None,
        tz_name: str = "Asia/Kolkata",
    ):
        self._sheet_id = sheet_id
        self._service_account_b64 = service_account_b64
        self._service_account_file = service_account_file
        self._tz_name = tz_name
        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None

    def _get_config(self) -> Tuple[str, str, str, str]:
        sheet_id = self._sheet_id or (current_app.config.get("GOOGLE_SHEET_ID") if current_app else "")
        b64 = self._service_account_b64 or (current_app.config.get("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64") if current_app else "")
        file_path = self._service_account_file or (current_app.config.get("GOOGLE_SERVICE_ACCOUNT_FILE_PATH") if current_app else "")
        tz_name = self._tz_name or (current_app.config.get("TIMEZONE") if current_app else "Asia/Kolkata")
        return sheet_id, b64, file_path, tz_name

    def is_configured(self) -> bool:
        """Checks whether sheet ID and valid credentials source exist."""
        sheet_id, b64, file_path, _ = self._get_config()
        has_creds = bool(b64 and b64 != "base64-encoded-service-account-json-string") or (
            bool(file_path and os.path.exists(file_path))
        )
        return bool(sheet_id and sheet_id != "your-google-sheet-id-here" and has_creds)

    def _repair_service_account_key(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Recalculates CRT parameters in RSA private key if copy-paste corrupted dmp1."""
        try:
            from pyasn1.codec.der import decoder
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization

            pk = info.get("private_key", "")
            pem_body = "".join(line for line in pk.split("\n") if not line.startswith("-----"))
            der = base64.b64decode(pem_body)
            obj, _ = decoder.decode(der)
            rsa_der = bytes(obj[2])
            rsa_obj, _ = decoder.decode(rsa_der)
            n = int(rsa_obj[1])
            e = int(rsa_obj[2])
            d = int(rsa_obj[3])
            p = int(rsa_obj[4])
            q = int(rsa_obj[5])
            dmp1 = d % (p - 1)
            dmq1 = d % (q - 1)
            iqmp = pow(q, -1, p)

            public_nums = rsa.RSAPublicNumbers(e, n)
            private_nums = rsa.RSAPrivateNumbers(p, q, d, dmp1, dmq1, iqmp, public_nums)
            key = private_nums.private_key()
            pem = key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()
            ).decode("utf-8")

            info_copy = dict(info)
            info_copy["private_key"] = pem
            return info_copy
        except Exception as exc:
            logger.warning("Could not auto-repair private key: %s", exc)
            return info

    def _get_credentials(self) -> Credentials:
        _, b64, file_path, _ = self._get_config()

        if b64 and b64 != "base64-encoded-service-account-json-string":
            try:
                decoded_bytes = base64.b64decode(b64.strip())
                info = json.loads(decoded_bytes.decode("utf-8"))
                try:
                    return Credentials.from_service_account_info(info, scopes=SCOPES)
                except ValueError as val_err:
                    if "Invalid private key" in str(val_err):
                        repaired_info = self._repair_service_account_key(info)
                        return Credentials.from_service_account_info(repaired_info, scopes=SCOPES)
                    raise
            except Exception as exc:
                raise ValueError(f"Failed to decode base64 service account JSON: {str(exc)}")

        if file_path and os.path.exists(file_path):
            return Credentials.from_service_account_file(file_path, scopes=SCOPES)

        raise ValueError("Google Sheets credentials are not configured in environment.")

    def get_spreadsheet(self) -> gspread.Spreadsheet:
        """Retrieves and caches the Google Spreadsheet instance."""
        if self._spreadsheet is None:
            sheet_id, _, _, _ = self._get_config()
            if not sheet_id:
                raise ValueError("GOOGLE_SHEET_ID is not configured.")
            creds = self._get_credentials()
            self._client = gspread.authorize(creds)
            try:
                self._spreadsheet = self._client.open_by_key(sheet_id)
            except SpreadsheetNotFound:
                raise ValueError(f"Spreadsheet with ID '{sheet_id}' was not found. Verify permissions and sheet ID.")
        return self._spreadsheet

    def _ensure_tab(self, tab_name: str, expected_headers: List[str]) -> gspread.Worksheet:
        """Gets or creates the worksheet tab, adding headers if empty."""
        spreadsheet = self.get_spreadsheet()
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows=500, cols=len(expected_headers))
            worksheet.append_row(expected_headers)
            return worksheet

        # Check existing headers in row 1
        existing_values = worksheet.row_values(1)
        if not existing_values:
            worksheet.append_row(expected_headers)
        return worksheet

    def _format_timestamp(self, ts_raw: Any) -> str:
        """Converts raw UTC timestamp to human-readable IST string."""
        _, _, _, tz_name = self._get_config()
        local_tz = pytz.timezone(tz_name)

        if not ts_raw:
            now_dt = datetime.now(pytz.utc).astimezone(local_tz)
            return now_dt.strftime("%Y-%m-%d %H:%M:%S IST")

        if isinstance(ts_raw, str):
            try:
                # Parse ISO format
                cleaned = ts_raw.replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(cleaned)
                if parsed_dt.tzinfo is None:
                    parsed_dt = pytz.utc.localize(parsed_dt)
                return parsed_dt.astimezone(local_tz).strftime("%Y-%m-%d %H:%M:%S IST")
            except Exception:
                return str(ts_raw)
        return str(ts_raw)

    def _execute_with_retry(self, operation_func, max_retries: int = 2):
        """Executes a gspread operation with bounded retry for transient errors."""
        for attempt in range(max_retries + 1):
            try:
                return operation_func()
            except APIError as api_err:
                status_code = getattr(api_err.response, "status_code", 0) if hasattr(api_err, "response") else 0
                if status_code in (429, 500, 502, 503) and attempt < max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise
            except Exception:
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                raise

    # -------------------------------------------------------------------------
    # Lead / Enquiry Sync
    # -------------------------------------------------------------------------

    def sync_lead(self, lead: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Idempotently synchronizes a lead to the 'Enquiries' tab.
        If Lead ID already exists in Column 1, duplicate row append is avoided.
        """
        if not self.is_configured():
            return False, "Google Sheets integration is not configured."

        lead_id = str(lead.get("id", "")).strip()
        if not lead_id:
            return False, "Lead ID is required for synchronization."

        try:
            def _op():
                ws = self._ensure_tab(TAB_ENQUIRIES, HEADERS_ENQUIRIES)
                col1_values = ws.col_values(1)

                if lead_id in col1_values:
                    logger.info("Lead %s already exists in sheet row %s. Skipping append.", lead_id, col1_values.index(lead_id) + 1)
                    return True, "Enquiry already synchronized in Google Sheet."

                submission_time = self._format_timestamp(lead.get("created_at"))
                row = [
                    lead_id,
                    submission_time,
                    lead.get("student_name", ""),
                    lead.get("phone_e164", ""),
                    lead.get("email", ""),
                    str(lead.get("class_level", "")),
                    str(lead.get("exam_goal", "")),
                    lead.get("interested_course", ""),
                ]
                ws.append_row(row, value_input_option="USER_ENTERED")
                return True, "Enquiry successfully synchronized to Google Sheet."

            return self._execute_with_retry(_op)
        except Exception as exc:
            sanitized = self._sanitize_error(exc)
            logger.error("Failed to sync lead %s to Google Sheet: %s", lead_id, sanitized)
            return False, sanitized

    # -------------------------------------------------------------------------
    # Booking Sync
    # -------------------------------------------------------------------------

    def sync_booking(self, booking: Dict[str, Any], student_name: str) -> Tuple[bool, str]:
        """
        Synchronizes a demo booking to the 'Demo Bookings' tab.
        Updates existing row if booking ID or lead ID is present; appends if new.
        """
        if not self.is_configured():
            return False, "Google Sheets integration is not configured."

        booking_id = str(booking.get("id", "")).strip()
        lead_id = str(booking.get("lead_id", "")).strip()
        if not booking_id or not lead_id:
            return False, "Booking ID and Lead ID are required for synchronization."

        try:
            def _op():
                ws = self._ensure_tab(TAB_BOOKINGS, HEADERS_BOOKINGS)
                col_booking_ids = ws.col_values(1)
                col_lead_ids = ws.col_values(2)

                row_idx = None
                if booking_id in col_booking_ids:
                    row_idx = col_booking_ids.index(booking_id) + 1
                elif lead_id in col_lead_ids:
                    row_idx = col_lead_ids.index(lead_id) + 1

                updated_time = self._format_timestamp(booking.get("updated_at") or booking.get("created_at"))
                slot_time = booking.get("slot_time", "")
                booking_status = booking.get("booking_status", "Booked")
                demo_date = str(booking.get("demo_date", ""))

                if row_idx and row_idx > 1:
                    # Update existing row in place
                    cell_range = f"A{row_idx}:G{row_idx}"
                    update_values = [[
                        booking_id,
                        lead_id,
                        student_name,
                        demo_date,
                        slot_time,
                        booking_status,
                        updated_time,
                    ]]
                    ws.update(range_name=cell_range, values=update_values)
                    return True, "Existing booking row updated in Google Sheet."
                else:
                    # Append new row
                    new_row = [
                        booking_id,
                        lead_id,
                        student_name,
                        demo_date,
                        slot_time,
                        booking_status,
                        updated_time,
                    ]
                    ws.append_row(new_row, value_input_option="USER_ENTERED")
                    return True, "Booking appended to Google Sheet."

            return self._execute_with_retry(_op)
        except Exception as exc:
            sanitized = self._sanitize_error(exc)
            logger.error("Failed to sync booking %s to Google Sheet: %s", booking_id, sanitized)
            return False, sanitized

    def _sanitize_error(self, exc: Exception) -> str:
        """Returns a safe, user-friendly error message without sensitive tokens."""
        msg = str(exc)
        if "403" in msg or "permission" in msg.lower():
            return "Permission denied: Ensure the Google Sheet is shared with your service account email as Editor."
        if "404" in msg or "not found" in msg.lower():
            return "Spreadsheet not found: Verify that GOOGLE_SHEET_ID is correct."
        if "429" in msg or "quota" in msg.lower():
            return "Google Sheets API quota exceeded. Please wait a moment before retrying."
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return "Google Sheets request timed out. Please retry."
        return f"Google Sheets API error: {msg[:120]}"

    def check_connection(self) -> Tuple[bool, str]:
        """Probes sheet connectivity for readiness health check."""
        if not self.is_configured():
            return False, "Google Sheets credentials not configured."
        try:
            ss = self.get_spreadsheet()
            return True, f"Google Sheet connected: '{ss.title}'"
        except Exception as exc:
            return False, self._sanitize_error(exc)


# Global service instance
google_sheets_service = GoogleSheetsService()
