-- BCE-1712: pipeline_schedules table + RLS
-- Parent: BCE-1711 (admin-controlled cron cadence for slide-pipeline)
--
-- Stage 1 of three:
--   Stage 1 (this migration) — pipeline_schedules table + RLS + admin allowlist source.
--   Stage 2 (BCE-1713) — slide-pipeline-cron workflow reads enabled/interval_minutes
--                         from this table before dispatching the run.
--   Stage 3 (BCE-1714) — static admin dashboard panel that updates this row via PostgREST.
--
-- Decision (admin allowlist mechanism):
--   Use a dedicated `admin_emails` table rather than an environment variable.
--   Reason: Supabase RLS policies need a queryable source of truth; env vars are not
--   exposed to RLS expressions without extra glue. Stage 3 will gate magic-link sign-in
--   directly against this table.

-- ============================================================================
-- admin_emails: source of truth for admin allowlist
-- ============================================================================
CREATE TABLE IF NOT EXISTS admin_emails (
  email text PRIMARY KEY,
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE admin_emails IS
  'Admin allowlist used by RLS policies (e.g. pipeline_schedules update). Stage 3 magic-link auth gates against this table. (BCE-1711/BCE-1712)';

ALTER TABLE admin_emails ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read own admin email"
  ON admin_emails
  FOR SELECT
  USING (
    auth.role() = 'authenticated'
    AND lower(email) = lower(auth.jwt() ->> 'email')
  );

CREATE POLICY "Service role manages admin emails"
  ON admin_emails
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

INSERT INTO admin_emails (email, note)
VALUES ('philoskor@gmail.com', 'BCE Lab founder / C-level (BCE-1712)')
ON CONFLICT (email) DO NOTHING;

-- ============================================================================
-- pipeline_schedules: dynamic schedule control for ops pipelines
-- ============================================================================
CREATE TABLE IF NOT EXISTS pipeline_schedules (
  pipeline_name text PRIMARY KEY,
  interval_minutes int NOT NULL CHECK (interval_minutes > 0),
  enabled bool NOT NULL DEFAULT true,
  last_run_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by text
);

COMMENT ON TABLE pipeline_schedules IS
  'Admin-controlled cadence for ops pipelines. Cron workflows read enabled/interval_minutes before dispatching; pipelines write last_run_at on success. (BCE-1711/BCE-1712)';
COMMENT ON COLUMN pipeline_schedules.pipeline_name IS 'Stable identifier, e.g. "slide-pipeline".';
COMMENT ON COLUMN pipeline_schedules.interval_minutes IS 'Minimum minutes between runs (admin-tunable).';
COMMENT ON COLUMN pipeline_schedules.enabled IS 'Whether the pipeline is allowed to dispatch.';
COMMENT ON COLUMN pipeline_schedules.last_run_at IS 'Timestamp of the most recent run, written by the pipeline itself.';
COMMENT ON COLUMN pipeline_schedules.updated_by IS 'Email of the user who last edited this row, or "system" for seed/automation.';

ALTER TABLE pipeline_schedules ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can view schedules"
  ON pipeline_schedules
  FOR SELECT
  USING (auth.role() = 'authenticated');

CREATE POLICY "Admin allowlist can update schedules"
  ON pipeline_schedules
  FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM admin_emails
      WHERE lower(admin_emails.email) = lower(auth.jwt() ->> 'email')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM admin_emails
      WHERE lower(admin_emails.email) = lower(auth.jwt() ->> 'email')
    )
  );

CREATE POLICY "Service role manages schedules"
  ON pipeline_schedules
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE OR REPLACE FUNCTION pipeline_schedules_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS pipeline_schedules_updated_at ON pipeline_schedules;
CREATE TRIGGER pipeline_schedules_updated_at
BEFORE UPDATE ON pipeline_schedules
FOR EACH ROW
EXECUTE FUNCTION pipeline_schedules_set_updated_at();

INSERT INTO pipeline_schedules (pipeline_name, interval_minutes, enabled, last_run_at, updated_at, updated_by)
VALUES ('slide-pipeline', 30, true, null, now(), 'system')
ON CONFLICT (pipeline_name) DO NOTHING;
