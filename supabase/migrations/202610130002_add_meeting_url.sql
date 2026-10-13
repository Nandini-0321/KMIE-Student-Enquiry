-- =============================================================================
-- Migration: 202610130002_add_meeting_url.sql
-- Adds optional meeting_url column to bookings table for dynamic class links.
-- =============================================================================

ALTER TABLE public.bookings
ADD COLUMN IF NOT EXISTS meeting_url TEXT NULL;

COMMENT ON COLUMN public.bookings.meeting_url IS 'Custom video conferencing link set by administrator for this specific demo appointment';
