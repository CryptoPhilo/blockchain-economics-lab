-- BCE: Remote pipeline state store.
--
-- GitHub Actions cannot call a local Paperclip instance. Runtime pipelines write
-- execution state here; Paperclip and static ops dashboards read this remote
-- source of truth instead of relying on local process logs.

CREATE TABLE IF NOT EXISTS public.pipeline_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_name text NOT NULL,
  paperclip_pipeline_name text,
  report_type text,
  project_slug text NOT NULL DEFAULT '__all__',
  version integer NOT NULL DEFAULT 1,
  source_file_id text,
  status text NOT NULL DEFAULT 'processing',
  source_filename text,
  retry_count integer NOT NULL DEFAULT 0,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  languages_completed jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_detail text,
  trigger_type text,
  dry_run boolean NOT NULL DEFAULT false,
  force boolean NOT NULL DEFAULT false,
  slug_filter text,
  summary text,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  artifact_path text,
  github_run_id text,
  github_run_number text,
  github_workflow text,
  github_sha text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.pipeline_node_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_run_id uuid NOT NULL REFERENCES public.pipeline_runs(id) ON DELETE CASCADE,
  pipeline_name text NOT NULL,
  node_key text NOT NULL,
  node_name text NOT NULL,
  status text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.pipeline_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_run_id uuid REFERENCES public.pipeline_runs(id) ON DELETE CASCADE,
  pipeline_name text NOT NULL,
  event_type text NOT NULL,
  severity text NOT NULL DEFAULT 'info',
  message text NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  artifact_ref text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at
  ON public.pipeline_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline_started
  ON public.pipeline_runs (pipeline_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_report_type_started
  ON public.pipeline_runs (report_type, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_node_runs_run
  ON public.pipeline_node_runs (pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_run
  ON public.pipeline_events (pipeline_run_id);

CREATE OR REPLACE FUNCTION public.pipeline_runs_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS pipeline_runs_updated_at ON public.pipeline_runs;
CREATE TRIGGER pipeline_runs_updated_at
  BEFORE UPDATE ON public.pipeline_runs
  FOR EACH ROW
  EXECUTE FUNCTION public.pipeline_runs_set_updated_at();

ALTER TABLE public.pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_node_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public can read pipeline runs" ON public.pipeline_runs;
CREATE POLICY "Public can read pipeline runs"
  ON public.pipeline_runs
  FOR SELECT
  USING (true);

DROP POLICY IF EXISTS "Public can read pipeline node runs" ON public.pipeline_node_runs;
CREATE POLICY "Public can read pipeline node runs"
  ON public.pipeline_node_runs
  FOR SELECT
  USING (true);

DROP POLICY IF EXISTS "Public can read pipeline events" ON public.pipeline_events;
CREATE POLICY "Public can read pipeline events"
  ON public.pipeline_events
  FOR SELECT
  USING (true);
