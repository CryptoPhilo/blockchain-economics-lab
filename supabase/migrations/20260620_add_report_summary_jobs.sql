-- BCE-2000: default-off Drive analysis Markdown summary candidate jobs
--
-- project_reports can store published source identity and card_data, but it is
-- not a stable place for pre-approval LLM candidate metadata. This table keeps
-- source revision/hash identity, model/prompt/schema versions, validation
-- status, and candidate patches out of production publication rows until a
-- remote approval explicitly allows promotion.

CREATE TABLE IF NOT EXISTS public.report_summary_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_identity text NOT NULL,
  source_drive_file_id text,
  source_revision_id text,
  source_sha256 text NOT NULL,
  source_name text NOT NULL,
  source_web_view_link text,
  project_slug text NOT NULL,
  report_type text NOT NULL,
  summarizer_model text NOT NULL,
  prompt_version text NOT NULL,
  schema_version text NOT NULL,
  generated_at timestamptz NOT NULL,
  validation_status text NOT NULL,
  status text NOT NULL,
  validation_errors jsonb NOT NULL DEFAULT '[]'::jsonb,
  candidate_patch jsonb NOT NULL DEFAULT '{}'::jsonb,
  llm_output jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.report_summary_jobs
  ADD COLUMN IF NOT EXISTS source_identity text,
  ADD COLUMN IF NOT EXISTS source_drive_file_id text,
  ADD COLUMN IF NOT EXISTS source_revision_id text,
  ADD COLUMN IF NOT EXISTS source_sha256 text,
  ADD COLUMN IF NOT EXISTS source_name text,
  ADD COLUMN IF NOT EXISTS source_web_view_link text,
  ADD COLUMN IF NOT EXISTS project_slug text,
  ADD COLUMN IF NOT EXISTS report_type text,
  ADD COLUMN IF NOT EXISTS summarizer_model text,
  ADD COLUMN IF NOT EXISTS prompt_version text,
  ADD COLUMN IF NOT EXISTS schema_version text,
  ADD COLUMN IF NOT EXISTS generated_at timestamptz,
  ADD COLUMN IF NOT EXISTS validation_status text,
  ADD COLUMN IF NOT EXISTS status text,
  ADD COLUMN IF NOT EXISTS validation_errors jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS candidate_patch jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS llm_output jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DROP INDEX IF EXISTS public.idx_report_summary_jobs_source_identity;

CREATE INDEX IF NOT EXISTS idx_report_summary_jobs_source_identity
  ON public.report_summary_jobs (source_identity);

CREATE INDEX IF NOT EXISTS idx_report_summary_jobs_project_type_status
  ON public.report_summary_jobs (project_slug, report_type, status);

COMMENT ON TABLE public.report_summary_jobs IS
  'Pre-publication LLM summary candidate jobs for Drive analysis Markdown sources. (BCE-2000)';
COMMENT ON COLUMN public.report_summary_jobs.source_identity IS
  'Source provenance: drive file id + revision id when available, otherwise normalized Markdown sha256. Not the authority-gate idempotency key.';
COMMENT ON COLUMN public.report_summary_jobs.candidate_patch IS
  'Validated project_reports patch candidate. Not applied to production rows without remote approval.';

ALTER TABLE public.report_summary_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role manages report summary jobs"
  ON public.report_summary_jobs
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Authenticated can view report summary jobs"
  ON public.report_summary_jobs
  FOR SELECT
  USING (auth.role() = 'authenticated');
