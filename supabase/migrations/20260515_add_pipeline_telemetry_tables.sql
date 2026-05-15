-- BCE-1900: Supabase-first report pipeline telemetry sink
--
-- The slide watcher writes durable run/node/event state here. Existing
-- consumers already read pipeline_runs, so this migration preserves the
-- legacy row contract while adding run-level metadata and child telemetry.

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_name text NOT NULL DEFAULT 'slide-pipeline',
  paperclip_pipeline_name text,
  report_type text NOT NULL,
  project_slug text,
  version int NOT NULL DEFAULT 1,
  status text NOT NULL,
  trigger_type text,
  summary text,
  source_file_id text,
  source_filename text,
  retry_count int NOT NULL DEFAULT 0,
  started_at timestamptz,
  completed_at timestamptz,
  languages_completed jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_detail text,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  artifact_path text,
  dry_run bool NOT NULL DEFAULT false,
  force bool NOT NULL DEFAULT false,
  slug_filter text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  github_run_id text,
  github_run_number text,
  github_workflow text,
  github_sha text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE pipeline_runs
  ADD COLUMN IF NOT EXISTS pipeline_name text NOT NULL DEFAULT 'slide-pipeline',
  ADD COLUMN IF NOT EXISTS paperclip_pipeline_name text,
  ADD COLUMN IF NOT EXISTS report_type text,
  ADD COLUMN IF NOT EXISTS project_slug text,
  ADD COLUMN IF NOT EXISTS version int NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS status text,
  ADD COLUMN IF NOT EXISTS trigger_type text,
  ADD COLUMN IF NOT EXISTS summary text,
  ADD COLUMN IF NOT EXISTS source_file_id text,
  ADD COLUMN IF NOT EXISTS source_filename text,
  ADD COLUMN IF NOT EXISTS retry_count int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS started_at timestamptz,
  ADD COLUMN IF NOT EXISTS completed_at timestamptz,
  ADD COLUMN IF NOT EXISTS languages_completed jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS error_detail text,
  ADD COLUMN IF NOT EXISTS metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS artifact_path text,
  ADD COLUMN IF NOT EXISTS dry_run bool NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS force bool NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS slug_filter text,
  ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS github_run_id text,
  ADD COLUMN IF NOT EXISTS github_run_number text,
  ADD COLUMN IF NOT EXISTS github_workflow text,
  ADD COLUMN IF NOT EXISTS github_sha text,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

COMMENT ON TABLE pipeline_runs IS
  'Durable Supabase telemetry/state store for report pipeline runs. Written by scripts/pipeline/watch_slides.py. (BCE-1900)';
COMMENT ON COLUMN pipeline_runs.metrics IS
  'Run-level counts including scanned, processed, published, review_ready, unresolved, failed, and blocked.';
COMMENT ON COLUMN pipeline_runs.artifact_path IS
  'Path to the run log artifact, usually logs/slide_pipeline/*.md.';

CREATE TABLE IF NOT EXISTS pipeline_node_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_run_id uuid NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  node_key text NOT NULL,
  node_name text NOT NULL,
  report_type text NOT NULL,
  status text NOT NULL,
  started_at timestamptz,
  finished_at timestamptz,
  summary text,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  artifact_path text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pipeline_node_runs IS
  'Per-node telemetry snapshots for report pipeline runs. (BCE-1900)';

CREATE TABLE IF NOT EXISTS pipeline_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_run_id uuid REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  severity text NOT NULL DEFAULT 'info',
  message text NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  artifact_path text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pipeline_events IS
  'Append-only event telemetry for report pipeline runs. (BCE-1900)';

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_name_started
  ON pipeline_runs (pipeline_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_report_type_started
  ON pipeline_runs (report_type, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status_started
  ON pipeline_runs (status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_node_runs_run
  ON pipeline_node_runs (pipeline_run_id, node_key);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_run
  ON pipeline_events (pipeline_run_id, occurred_at DESC);

ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_node_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role manages pipeline runs"
  ON pipeline_runs
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Authenticated can view pipeline runs"
  ON pipeline_runs
  FOR SELECT
  USING (auth.role() = 'authenticated');

CREATE POLICY "Service role manages pipeline node runs"
  ON pipeline_node_runs
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Authenticated can view pipeline node runs"
  ON pipeline_node_runs
  FOR SELECT
  USING (auth.role() = 'authenticated');

CREATE POLICY "Service role manages pipeline events"
  ON pipeline_events
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Authenticated can view pipeline events"
  ON pipeline_events
  FOR SELECT
  USING (auth.role() = 'authenticated');
