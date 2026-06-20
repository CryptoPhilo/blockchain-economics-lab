-- BCE-2002: Summary Authority Gate DB contract.
--
-- This migration keeps Drive analysis Markdown summary candidates out of
-- project_reports until an explicit promotion gate approves them. The gate is
-- default-off at the service layer; these columns/tables store state,
-- idempotency, locking, and audit evidence for that later decision.

ALTER TABLE public.report_summary_jobs
  ADD COLUMN IF NOT EXISTS report_code text,
  ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'ko',
  ADD COLUMN IF NOT EXISTS idempotency_key text,
  ADD COLUMN IF NOT EXISTS authority_state text NOT NULL DEFAULT 'detected',
  ADD COLUMN IF NOT EXISTS authority_mode text NOT NULL DEFAULT 'legacy_script',
  ADD COLUMN IF NOT EXISTS validator_result jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS promotion_requested_at timestamptz,
  ADD COLUMN IF NOT EXISTS promotion_started_at timestamptz,
  ADD COLUMN IF NOT EXISTS promoted_at timestamptz,
  ADD COLUMN IF NOT EXISTS rejected_at timestamptz,
  ADD COLUMN IF NOT EXISTS fallback_at timestamptz,
  ADD COLUMN IF NOT EXISTS promotion_actor text,
  ADD COLUMN IF NOT EXISTS promotion_decision text,
  ADD COLUMN IF NOT EXISTS promotion_decision_reason text,
  ADD COLUMN IF NOT EXISTS promoted_project_report_id uuid REFERENCES public.project_reports(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS promotion_audit jsonb NOT NULL DEFAULT '{}'::jsonb;

UPDATE public.report_summary_jobs
SET
  report_code = COALESCE(report_code, report_type, 'unknown'),
  locale = COALESCE(locale, 'ko'),
  idempotency_key = COALESCE(
    idempotency_key,
    concat_ws(
      ':',
      COALESCE(report_type, report_code, 'unknown'),
      COALESCE(project_slug, 'unknown'),
      COALESCE(locale, 'ko'),
      COALESCE(source_drive_file_id, 'local'),
      COALESCE(source_revision_id, source_sha256, source_identity, 'unknown-source'),
      COALESCE(prompt_version, 'unknown-prompt'),
      COALESCE(schema_version, 'unknown-schema')
    )
  ),
  authority_state = CASE
    WHEN authority_state IS NOT NULL AND authority_state <> 'detected' THEN authority_state
    WHEN status = 'validation_failed' OR validation_status = 'invalid' THEN 'validation_failed'
    WHEN status IN ('candidate_ready', 'validation_passed') OR validation_status = 'valid' THEN 'validation_passed'
    ELSE 'detected'
  END,
  validator_result = CASE
    WHEN validator_result <> '{}'::jsonb THEN validator_result
    ELSE jsonb_build_object(
      'validation_status', validation_status,
      'validation_errors', validation_errors
    )
  END
WHERE idempotency_key IS NULL
   OR report_code IS NULL
   OR authority_state = 'detected'
   OR validator_result = '{}'::jsonb;

ALTER TABLE public.report_summary_jobs
  ALTER COLUMN report_code SET NOT NULL,
  ALTER COLUMN idempotency_key SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'report_summary_jobs_authority_state_check'
      AND conrelid = 'public.report_summary_jobs'::regclass
  ) THEN
    ALTER TABLE public.report_summary_jobs
      ADD CONSTRAINT report_summary_jobs_authority_state_check
      CHECK (
        authority_state IN (
          'detected',
          'llm_candidate',
          'validation_failed',
          'validation_passed',
          'promotion_pending',
          'promoted',
          'rejected',
          'fallback_script'
        )
      );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'report_summary_jobs_authority_mode_check'
      AND conrelid = 'public.report_summary_jobs'::regclass
  ) THEN
    ALTER TABLE public.report_summary_jobs
      ADD CONSTRAINT report_summary_jobs_authority_mode_check
      CHECK (authority_mode IN ('legacy_script', 'llm_candidate', 'llm_active'));
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_report_summary_jobs_idempotency_key
  ON public.report_summary_jobs (idempotency_key);

CREATE INDEX IF NOT EXISTS idx_report_summary_jobs_authority_queue
  ON public.report_summary_jobs (authority_state, authority_mode, project_slug, report_type, locale);

CREATE TABLE IF NOT EXISTS public.report_summary_promotion_locks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_slug text NOT NULL,
  report_type text NOT NULL,
  locale text NOT NULL DEFAULT 'ko',
  job_id uuid NOT NULL REFERENCES public.report_summary_jobs(id) ON DELETE CASCADE,
  actor text,
  acquired_at timestamptz NOT NULL DEFAULT now(),
  released_at timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_report_summary_promotion_locks_active
  ON public.report_summary_promotion_locks (project_slug, report_type, locale)
  WHERE released_at IS NULL;

COMMENT ON COLUMN public.report_summary_jobs.idempotency_key IS
  'Authority-gate idempotency key: reportCode + reportSlug + locale + driveFileId + revision/hash + promptVersion + schemaVersion.';
COMMENT ON COLUMN public.report_summary_jobs.authority_state IS
  'Summary Authority Gate state machine: detected -> llm_candidate -> validation_failed|validation_passed -> promotion_pending -> promoted|rejected|fallback_script.';
COMMENT ON COLUMN public.report_summary_jobs.authority_mode IS
  'Read/promotion mode: legacy_script, llm_candidate, or llm_active.';
COMMENT ON COLUMN public.report_summary_jobs.promotion_audit IS
  'Promotion/rejection/fallback audit payload including source identity, validator result, actor, decision, and target report row.';
COMMENT ON TABLE public.report_summary_promotion_locks IS
  'Active promotion lock for one project_slug/report_type/locale at a time.';

CREATE OR REPLACE FUNCTION public.promote_report_summary_job(
  p_job_id uuid,
  p_actor text,
  p_authority_mode text,
  p_reason text DEFAULT 'validated candidate promoted to project_reports'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_job public.report_summary_jobs%ROWTYPE;
  v_target public.project_reports%ROWTYPE;
  v_project_id uuid;
  v_now timestamptz := now();
  v_audit jsonb;
  v_card_data jsonb;
BEGIN
  IF p_authority_mode <> 'llm_active' THEN
    RAISE EXCEPTION 'authority mode % cannot promote through active gate', p_authority_mode;
  END IF;

  SELECT *
  INTO v_job
  FROM public.report_summary_jobs
  WHERE id = p_job_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'report_summary_jobs row not found: %', p_job_id;
  END IF;

  IF v_job.authority_state <> 'validation_passed'
     OR COALESCE(v_job.validation_status, 'valid') <> 'valid' THEN
    RAISE EXCEPTION 'candidate is not validation_passed';
  END IF;

  INSERT INTO public.report_summary_promotion_locks (
    project_slug,
    report_type,
    locale,
    job_id,
    actor,
    acquired_at
  )
  VALUES (
    v_job.project_slug,
    v_job.report_type,
    COALESCE(v_job.locale, 'ko'),
    v_job.id,
    p_actor,
    v_now
  );

  SELECT id
  INTO v_project_id
  FROM public.tracked_projects
  WHERE slug = v_job.project_slug
  LIMIT 1;

  IF v_project_id IS NULL THEN
    RAISE EXCEPTION 'tracked project not found: %', v_job.project_slug;
  END IF;

  SELECT *
  INTO v_target
  FROM public.project_reports
  WHERE project_id = v_project_id
    AND report_type = v_job.report_type
    AND language = COALESCE(v_job.locale, 'ko')
    AND status IN ('published', 'coming_soon', 'in_review')
    AND (
      (v_job.candidate_patch #>> '{card_data,source_md,version}') IS NULL
      OR version = (v_job.candidate_patch #>> '{card_data,source_md,version}')::integer
    )
  LIMIT 1
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION
      'website-visible project_reports target not found: %/%/%',
      v_job.project_slug,
      v_job.report_type,
      COALESCE(v_job.locale, 'ko');
  END IF;

  v_card_data :=
    COALESCE(v_target.card_data, '{}'::jsonb)
    || COALESCE(v_job.candidate_patch -> 'card_data', '{}'::jsonb)
    || jsonb_build_object(
      'summary_authority',
      jsonb_build_object(
        'mode', 'llm_active',
        'job_id', v_job.id,
        'source_identity', v_job.source_identity,
        'idempotency_key', v_job.idempotency_key,
        'promoted_at', v_now
      )
    );

  UPDATE public.project_reports
  SET
    card_data = v_card_data,
    marketing_content_by_lang = COALESCE(v_job.candidate_patch -> 'marketing_content_by_lang', marketing_content_by_lang),
    summary_source_md_file_id = COALESCE(v_job.candidate_patch ->> 'summary_source_md_file_id', summary_source_md_file_id),
    summary_source_md_name = COALESCE(v_job.candidate_patch ->> 'summary_source_md_name', summary_source_md_name),
    summary_source_md_archived_url = COALESCE(v_job.candidate_patch ->> 'summary_source_md_archived_url', summary_source_md_archived_url),
    summary_generated_at = COALESCE((v_job.candidate_patch ->> 'summary_generated_at')::timestamptz, summary_generated_at),
    card_summary_ko = COALESCE(v_job.candidate_patch ->> 'card_summary_ko', card_summary_ko),
    card_summary_en = COALESCE(v_job.candidate_patch ->> 'card_summary_en', card_summary_en),
    card_summary_fr = COALESCE(v_job.candidate_patch ->> 'card_summary_fr', card_summary_fr),
    card_summary_es = COALESCE(v_job.candidate_patch ->> 'card_summary_es', card_summary_es),
    card_summary_de = COALESCE(v_job.candidate_patch ->> 'card_summary_de', card_summary_de),
    card_summary_ja = COALESCE(v_job.candidate_patch ->> 'card_summary_ja', card_summary_ja),
    card_summary_zh = COALESCE(v_job.candidate_patch ->> 'card_summary_zh', card_summary_zh),
    risk_level = COALESCE(v_job.candidate_patch ->> 'risk_level', risk_level),
    card_risk_score = COALESCE((v_job.candidate_patch ->> 'card_risk_score')::integer, card_risk_score),
    updated_at = v_now
  WHERE id = v_target.id;

  v_audit := COALESCE(v_job.promotion_audit, '{}'::jsonb) || jsonb_build_object(
    'source_identity', v_job.source_identity,
    'source_sha256', v_job.source_sha256,
    'source_revision_id', v_job.source_revision_id,
    'summarizer_model', v_job.summarizer_model,
    'prompt_version', v_job.prompt_version,
    'schema_version', v_job.schema_version,
    'validator_result', v_job.validator_result,
    'actor', p_actor,
    'decision', 'promote',
    'decision_reason', p_reason,
    'project_report_id', v_target.id,
    'decided_at', v_now
  );

  UPDATE public.report_summary_jobs
  SET
    authority_state = 'promoted',
    authority_mode = 'llm_active',
    promotion_started_at = COALESCE(promotion_started_at, v_now),
    promoted_at = v_now,
    promotion_actor = p_actor,
    promotion_decision = 'promote',
    promotion_decision_reason = p_reason,
    promoted_project_report_id = v_target.id,
    promotion_audit = v_audit,
    updated_at = v_now
  WHERE id = v_job.id;

  INSERT INTO public.pipeline_events (
    pipeline_run_id,
    event_type,
    severity,
    message,
    details,
    occurred_at
  )
  VALUES (
    NULL,
    'summary_authority_gate.promoted',
    'info',
    'Summary Authority Gate promoted validated candidate',
    jsonb_build_object(
      'pipeline', 'analysis-md-summary-candidate',
      'node', 'summary_authority_gate',
      'job_id', v_job.id,
      'project_slug', v_job.project_slug,
      'report_type', v_job.report_type,
      'locale', COALESCE(v_job.locale, 'ko'),
      'project_report_id', v_target.id,
      'authority_mode', p_authority_mode
    ),
    v_now
  );

  UPDATE public.report_summary_promotion_locks
  SET released_at = v_now
  WHERE job_id = v_job.id
    AND released_at IS NULL;

  RETURN jsonb_build_object(
    'job_id', v_job.id,
    'project_report_id', v_target.id,
    'authority_state', 'promoted'
  );
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'active promotion lock exists';
END;
$$;

COMMENT ON FUNCTION public.promote_report_summary_job(uuid, text, text, text) IS
  'Atomically promotes a validation-passed report_summary_jobs row into project_reports with audit/event writes and promotion lock handling.';

ALTER TABLE public.report_summary_promotion_locks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role manages report summary promotion locks"
  ON public.report_summary_promotion_locks
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Authenticated can view report summary promotion locks"
  ON public.report_summary_promotion_locks
  FOR SELECT
  USING (auth.role() = 'authenticated');
