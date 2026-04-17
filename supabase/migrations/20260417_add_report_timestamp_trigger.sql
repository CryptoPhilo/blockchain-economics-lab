-- BCE-233: Auto-update tracked_projects report timestamps when reports are published
-- This trigger ensures last_econ_report_at, last_maturity_report_at, and last_forensic_report_at
-- are automatically updated when corresponding reports are published

-- 1. Function to update tracked_projects report timestamps
CREATE OR REPLACE FUNCTION update_tracked_project_report_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  -- Only update if status changed to 'published' or 'coming_soon'
  IF (NEW.status = 'published' OR NEW.status = 'coming_soon')
     AND (TG_OP = 'INSERT' OR OLD.status != NEW.status OR OLD.published_at != NEW.published_at) THEN

    -- Update the corresponding timestamp based on report_type
    IF NEW.report_type = 'econ' THEN
      UPDATE tracked_projects
      SET last_econ_report_at = COALESCE(NEW.published_at, NEW.updated_at, now())
      WHERE id = NEW.project_id;

    ELSIF NEW.report_type = 'maturity' THEN
      UPDATE tracked_projects
      SET last_maturity_report_at = COALESCE(NEW.published_at, NEW.updated_at, now())
      WHERE id = NEW.project_id;

    ELSIF NEW.report_type = 'forensic' THEN
      UPDATE tracked_projects
      SET last_forensic_report_at = COALESCE(NEW.published_at, NEW.updated_at, now())
      WHERE id = NEW.project_id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Create trigger on project_reports
DROP TRIGGER IF EXISTS update_project_report_timestamp ON project_reports;

CREATE TRIGGER update_project_report_timestamp
  AFTER INSERT OR UPDATE ON project_reports
  FOR EACH ROW
  EXECUTE FUNCTION update_tracked_project_report_timestamp();

-- 3. Backfill existing data: sync current published reports to tracked_projects
-- This will update all existing projects with their most recent report timestamps
UPDATE tracked_projects tp
SET last_econ_report_at = (
  SELECT MAX(published_at)
  FROM project_reports pr
  WHERE pr.project_id = tp.id
    AND pr.report_type = 'econ'
    AND pr.status IN ('published', 'coming_soon')
);

UPDATE tracked_projects tp
SET last_maturity_report_at = (
  SELECT MAX(published_at)
  FROM project_reports pr
  WHERE pr.project_id = tp.id
    AND pr.report_type = 'maturity'
    AND pr.status IN ('published', 'coming_soon')
);

UPDATE tracked_projects tp
SET last_forensic_report_at = (
  SELECT MAX(published_at)
  FROM project_reports pr
  WHERE pr.project_id = tp.id
    AND pr.report_type = 'forensic'
    AND pr.status IN ('published', 'coming_soon')
);
