# KMIE Student Enquiry & Demo Booking Automation
## 3-to-5 Minute Assessment Demonstration Script

**Candidate:** Nandini R  
**Role:** Software Developer & Automation Intern  
**Project:** KMIE Student Enquiry & Demo Booking Automation  

---

## Demonstration Overview

| Stage | Flow Demonstrated | Key Assessment Mark Area |
|---|---|---|
| **Part 1** | New Student Enquiry Submission & Persistence | Part A (15 Marks) |
| **Part 2** | Duplicate Phone Prevention with Varied Formatting | Part B (10 Marks) |
| **Part 3** | Demo Appointment Booking & Rescheduling | Part C (15 Marks) |
| **Part 4** | Protected Admin Dashboard & Failure Recovery | Part D (10 Marks) |

---

## Step-by-Step Walkthrough

### Part 1: Submit a New Valid Enquiry (Part A — 15 Marks)

1. **Action**: Open the web application homepage (`http://localhost:5000/` or live Render URL).
2. **Action**: Complete the Student Enquiry Form with test information:
   - **Student Full Name**: `Aarav Sharma`
   - **Phone Number**: `9876543210` *(Standard 10-digit Indian number)*
   - **Email Address**: `aarav.sharma@example.com`
   - **Current Class**: `Class 11`
   - **Target Exam Goal**: `NEET`
   - **Interested Course**: `NEET Long-Term Preparation`
3. **Action**: Click **"Submit Enquiry & Proceed to Demo Slot"**.
4. **Expected Result**:
   - The enquiry submission screen appears.
   - The phone number is canonicalized to E.164 (`+919876543210`) and safely masked on screen as `+9198*****10`.
   - A green sync indicator appears showing `✓ Google Sheets Synchronized` (or `Sync Queued` if running offline).
   - In Supabase `leads` table: A new record is created with UUID primary key.
   - In Google Sheet `Enquiries` tab: A new row is appended with formatted submission timestamp in India Standard Time (`IST`).

---

### Part 2: Duplicate Lead Prevention Test (Part B — 10 Marks)

1. **Action**: Navigate back to the homepage (`/`).
2. **Action**: Submit the form again using the **exact same student phone number, but formatted with country code, spaces, and hyphens**:
   - **Student Full Name**: `Aarav Sharma (Duplicate Test)`
   - **Phone Number**: `+91 98765-43210` *(Notice difference: +91 prefix, space, hyphen)*
   - **Email Address**: `aarav.duplicate@example.com`
   - **Class**: `Class 11`
   - **Exam Goal**: `NEET`
   - **Interested Course**: `NEET Crash Course`
3. **Action**: Click **"Submit Enquiry"**.
4. **Expected Result**:
   - The application intercepts the duplicate and displays the **Existing Registration Found** warning card.
   - Notice displayed: *"An enquiry associated with phone number +9198*****10 is already registered in our system."*
   - **Verification**:
     - Check Supabase `leads` table: **No second lead record is created**.
     - Check Google Sheets `Enquiries` tab: **No duplicate row is appended**.
   - The user is provided with a secure action to proceed directly to book or manage their demo slot using a signed token.

---

### Part 3: Demo Slot Appointment Scheduling (Part C — 15 Marks)

1. **Action**: Click **"Proceed to Demo Slot Booking / Reschedule"** (or open the booking link).
2. **Action**: Review the booking form:
   - Notice the four required time slots: `1:00 PM IST (13:00)`, `3:00 PM IST (15:00)`, `5:00 PM IST (17:00)`, `7:00 PM IST (19:00)`.
   - Notice that dates in the past are disabled in the date picker.
3. **Action**: Select a future date (e.g. tomorrow) and select the **3:00 PM IST** slot.
4. **Action**: Click **"Confirm Demo Class Booking"**.
5. **Expected Result**:
   - The **Demo Class Confirmed!** page displays:
     - Student Name: `Aarav Sharma`
     - Selected Demo Date: `[Selected Date]`
     - Session Slot: `3:00 PM IST (15:00)`
     - Booking Status: `Booked`
     - Meeting Link Box: Displays the configured placeholder Zoom link (`https://zoom.us/j/placeholder-kmie-demo-session`), with clear disclaimer that this is a placeholder URL for assessment purposes.
   - In Supabase `bookings` table: Record is inserted referencing `lead_id`.
   - In Google Sheet `Demo Bookings` tab: Row is appended with Booking ID, Lead ID, Student Name, Date, Time, and Status (`Booked`).

---

### Part 4: Admin Management & Status Transitions (Part C & D — 10 Marks)

1. **Action**: Navigate to `/admin/login`.
2. **Action**: Sign in using administrator credentials (`admin` / configured password).
3. **Action**: Review the **Admissions & Bookings Management Dashboard**:
   - Overview metrics card displays total leads, demo bookings, and pending sync counts.
   - Search/filter bar: Filter by exam goal (`NEET`), class (`11`), or search for `Aarav`.
   - Locate `Aarav Sharma`'s row in the table.
4. **Action (Status Update)**:
   - Change the booking status dropdown from **Booked** to **Attended**.
   - The change automatically persists to Supabase and triggers an in-place update in the Google Sheet `Demo Bookings` row.
5. **Action (Rescheduling)**:
   - Click the **Reschedule** action dropdown on the lead's row.
   - Choose a different slot (e.g. `5:00 PM IST`) and click **Save Slot**.
   - Verify that the existing booking record is updated rather than creating a duplicate booking.

---

### Part 5: Failure Recovery Scenario (Part D — 10 Marks)

1. **Explanation to Evaluator**:
   *"What happens if Google Sheets API undergoes a temporary network outage or rate-limiting?"*
2. **Demonstration**:
   - When Google Sheets API fails or is temporarily unreachable:
     - The enquiry is **safely committed to Supabase PostgreSQL**, preserving the student's lead.
     - The application does **not crash** or falsely tell the student that their submission was lost.
     - The student is notified that their enquiry was saved and spreadsheet sync is pending.
     - In Supabase, `sheet_sync_status` is marked as `'failed'` with a sanitized diagnostic message recorded.
   - **Recovery**:
     - When Google Sheets connectivity is restored, the administrator clicks **"Retry All Pending Syncs"** on the admin dashboard.
     - The system re-syncs the queued records idempotently **without producing duplicate rows in the spreadsheet**.

---

## Summary of Assessment Compliance

- **Part A (15 Marks)**: Student enquiry form with all 6 required fields, Supabase storage, Google Sheets sync, success/error feedback.
- **Part B (10 Marks)**: Canonical E.164 phone normalization across formats (spaces, hyphens, country code, leading `00`), duplicate lead rejection, automated tests.
- **Part C (15 Marks)**: Demo booking on future dates, 4 fixed time slots (`13:00`, `15:00`, `17:00`, `19:00`), 3 booking statuses (`Booked`, `Attended`, `Not Attended`), placeholder Zoom confirmation.
- **Part D (10 Marks)**: Complete walkthrough script, end-to-end data lifecycle explanation, and robust failure recovery demonstration.
