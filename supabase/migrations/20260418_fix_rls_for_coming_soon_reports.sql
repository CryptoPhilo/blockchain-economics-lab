-- Migration: Fix RLS policy to allow public access to coming_soon reports
-- Date: 2026-04-18
-- Issue: BCE-375
-- Description: The /reports page shows FOR reports within 72 hours, including both
--              'published' and 'coming_soon' status (per OPS-007). However, the RLS
--              policy only allowed 'published' reports, filtering out all coming_soon
--              reports from anonymous users. This migration updates the policy to
--              include both statuses.

-- Drop the old restrictive policy
DROP POLICY IF EXISTS "Public can view published reports" ON project_reports;

-- Create new policy that allows both published and coming_soon reports
CREATE POLICY "Public can view published and coming soon reports"
  ON project_reports
  FOR SELECT
  USING (status IN ('published', 'coming_soon'));

-- Note: This aligns with the frontend implementation in src/app/[locale]/reports/page.tsx
-- which explicitly queries for both statuses (line 81-82)
