-- =============================================================================
-- KMIE STUDENT ENQUIRY & DEMO BOOKING AUTOMATION
-- Database Migration: 202610130001_init.sql
-- PostgreSQL / Supabase Schema Definition
-- =============================================================================

-- Ensure required extensions exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- Helper function to automatically update `updated_at` timestamps
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1. LEADS TABLE
-- Primary source of truth for student enquiries.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_name VARCHAR(120) NOT NULL,
    phone_e164 VARCHAR(32) NOT NULL,
    email VARCHAR(255) NOT NULL,
    class_level VARCHAR(10) NOT NULL,
    exam_goal VARCHAR(10) NOT NULL,
    interested_course VARCHAR(120) NOT NULL,
    sheet_sync_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    sheet_synced_at TIMESTAMPTZ NULL,
    sheet_sync_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    -- Constraints
    CONSTRAINT uq_leads_phone_e164 UNIQUE (phone_e164),
    CONSTRAINT chk_leads_class_level CHECK (class_level IN ('11', '12')),
    CONSTRAINT chk_leads_exam_goal CHECK (exam_goal IN ('NEET', 'JEE')),
    CONSTRAINT chk_leads_sheet_sync_status CHECK (sheet_sync_status IN ('pending', 'synced', 'failed')),
    CONSTRAINT chk_leads_student_name_length CHECK (char_length(student_name) >= 2)
);

-- Indexes for performance and duplicate lookups
CREATE INDEX IF NOT EXISTS idx_leads_phone_e164 ON public.leads(phone_e164);
CREATE INDEX IF NOT EXISTS idx_leads_created_at_desc ON public.leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_sheet_sync_status ON public.leads(sheet_sync_status);

-- Auto-update updated_at trigger for leads
DROP TRIGGER IF EXISTS trg_leads_updated_at ON public.leads;
CREATE TRIGGER trg_leads_updated_at
    BEFORE UPDATE ON public.leads
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 2. DEMO BOOKINGS TABLE
-- Maintains demo slot appointments linked to leads.
-- Enforces 1 current booking per lead via UNIQUE(lead_id).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    demo_date DATE NOT NULL,
    slot_time VARCHAR(10) NOT NULL,
    booking_status VARCHAR(20) NOT NULL DEFAULT 'Booked',
    sheet_sync_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    sheet_synced_at TIMESTAMPTZ NULL,
    sheet_sync_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    -- Constraints
    CONSTRAINT uq_bookings_lead_id UNIQUE (lead_id),
    CONSTRAINT chk_bookings_slot_time CHECK (slot_time IN ('13:00', '15:00', '17:00', '19:00')),
    CONSTRAINT chk_bookings_status CHECK (booking_status IN ('Booked', 'Attended', 'Not Attended')),
    CONSTRAINT chk_bookings_sheet_sync_status CHECK (sheet_sync_status IN ('pending', 'synced', 'failed'))
);

-- Indexes for booking lookups
CREATE INDEX IF NOT EXISTS idx_bookings_lead_id ON public.bookings(lead_id);
CREATE INDEX IF NOT EXISTS idx_bookings_demo_date ON public.bookings(demo_date);
CREATE INDEX IF NOT EXISTS idx_bookings_sheet_sync_status ON public.bookings(sheet_sync_status);

-- Auto-update updated_at trigger for bookings
DROP TRIGGER IF EXISTS trg_bookings_updated_at ON public.bookings;
CREATE TRIGGER trg_bookings_updated_at
    BEFORE UPDATE ON public.bookings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 3. ROW LEVEL SECURITY (RLS) POLICIES
-- Block unauthenticated public access. Backend service_role key has bypass
-- privileges for server-side operations.
-- -----------------------------------------------------------------------------
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;

-- Deny all public anon operations by default
DROP POLICY IF EXISTS "Deny public anon access to leads" ON public.leads;
CREATE POLICY "Deny public anon access to leads"
    ON public.leads
    FOR ALL
    TO anon
    USING (false);

DROP POLICY IF EXISTS "Deny public anon access to bookings" ON public.bookings;
CREATE POLICY "Deny public anon access to bookings"
    ON public.bookings
    FOR ALL
    TO anon
    USING (false);

-- Comments for documentation in Supabase Studio
COMMENT ON TABLE public.leads IS 'Captures student admission enquiries with canonical E.164 phone numbers';
COMMENT ON TABLE public.bookings IS 'Demo appointment scheduling associated with unique lead records';
