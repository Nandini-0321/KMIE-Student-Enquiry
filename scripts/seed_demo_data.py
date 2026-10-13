"""
Demo Data Seeding Script for KMIE Automation Assessment.
Reads fictitious sample records from sample_data/enquiries.csv and inserts them
idempotently into Supabase PostgreSQL, and optionally synchronizes to Google Sheets.

Usage:
    python scripts/seed_demo_data.py [--sync-sheets]
"""
import csv
import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.services.phone_service import normalize_phone_number
from app.services.supabase_service import supabase_service
from app.services.google_sheets_service import google_sheets_service


def seed_demo_data(sync_to_sheets: bool = False):
    """Inserts sample enquiry records idempotently."""
    csv_file = BASE_DIR / "sample_data" / "enquiries.csv"
    if not csv_file.exists():
        print(f"Error: Sample data file not found at {csv_file}")
        sys.exit(1)

    app = create_app(os.getenv("APP_ENV", "development"))

    with app.app_context():
        if not supabase_service.is_configured():
            print("Notice: Supabase is not configured in the current environment.")
            print("Please set SUPABASE_URL and SUPABASE_SECRET_KEY in your .env file.")
            sys.exit(1)

        print(f"\n--- Loading Fictitious Sample Enquiries from {csv_file.name} ---")
        inserted_count = 0
        skipped_count = 0

        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row["student_name"].strip()
                raw_phone = row["phone_number"].strip()
                email = row["email"].strip()
                class_level = row["class_level"].strip()
                exam_goal = row["exam_goal"].strip()
                course = row["interested_course"].strip()

                is_valid, phone_e164, _ = normalize_phone_number(raw_phone)
                if not is_valid:
                    print(f"  [SKIPPED] Invalid phone '{raw_phone}' for {name}: {phone_e164}")
                    continue

                # Idempotency check: Does phone already exist?
                existing = supabase_service.find_lead_by_phone(phone_e164)
                if existing:
                    print(f"  [EXISTS] Lead for {name} ({phone_e164}) already present (ID: {existing['id'][:8]}...).")
                    skipped_count += 1
                    target_lead = existing
                else:
                    lead_payload = {
                        "student_name": name,
                        "phone_e164": phone_e164,
                        "email": email,
                        "class_level": class_level,
                        "exam_goal": exam_goal,
                        "interested_course": course,
                    }
                    success, new_lead, err = supabase_service.create_lead(lead_payload)
                    if success and new_lead:
                        print(f"  [INSERTED] Created demo lead: {name} | {phone_e164} (ID: {new_lead['id'][:8]}...)")
                        inserted_count += 1
                        target_lead = new_lead
                    else:
                        print(f"  [ERROR] Failed to insert {name}: {err}")
                        continue

                # Optional Google Sheets synchronization
                if sync_to_sheets:
                    if google_sheets_service.is_configured():
                        synced, s_msg = google_sheets_service.sync_lead(target_lead)
                        if synced:
                            supabase_service.update_lead_sheet_sync(target_lead["id"], "synced")
                            print(f"    -> Synced to Google Sheets: {s_msg}")
                        else:
                            supabase_service.update_lead_sheet_sync(target_lead["id"], "failed", s_msg)
                            print(f"    -> Google Sheets sync failed: {s_msg}")
                    else:
                        print("    -> Google Sheets not configured; skipping sync.")

        print("\n--- Seeding Summary ---")
        print(f"New Records Inserted : {inserted_count}")
        print(f"Existing Records Kept: {skipped_count}")
        print("Done.\n")


if __name__ == "__main__":
    sync_flag = "--sync-sheets" in sys.argv
    seed_demo_data(sync_to_sheets=sync_flag)
