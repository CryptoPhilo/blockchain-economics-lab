-- Quick Fix for BCE-375: Allow public access to coming_soon reports
-- Copy and paste this entire block into Supabase Dashboard > SQL Editor

-- Drop old policy
DROP POLICY IF EXISTS "Public can view published reports" ON project_reports;

-- Create new policy allowing both published and coming_soon
CREATE POLICY "Public can view published and coming soon reports"
  ON project_reports
  FOR SELECT
  USING (status IN ('published', 'coming_soon'));

-- Verification query (should return 28)
SELECT count(*) as total_for_reports_72h
FROM project_reports
WHERE report_type = 'forensic'
  AND status IN ('published', 'coming_soon')
  AND created_at >= NOW() - INTERVAL '72 hours';
