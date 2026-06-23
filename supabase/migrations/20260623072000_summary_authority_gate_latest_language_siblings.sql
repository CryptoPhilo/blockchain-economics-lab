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
  v_candidate_version integer;
  v_updated_report_count integer := 0;
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

  v_candidate_version := NULLIF(v_job.candidate_patch #>> '{card_data,source_md,version}', '')::integer;

  SELECT *
  INTO v_target
  FROM public.project_reports
  WHERE project_id = v_project_id
    AND report_type::text = v_job.report_type
    AND language = COALESCE(v_job.locale, 'ko')
    AND status IN ('published', 'coming_soon', 'in_review')
    AND version = v_candidate_version
  LIMIT 1
  FOR UPDATE;

  IF NOT FOUND THEN
    SELECT *
    INTO v_target
    FROM public.project_reports
    WHERE project_id = v_project_id
      AND report_type::text = v_job.report_type
      AND language = COALESCE(v_job.locale, 'ko')
      AND status IN ('published', 'coming_soon', 'in_review')
    ORDER BY version DESC
    LIMIT 1
    FOR UPDATE;
  END IF;

  IF NOT FOUND THEN
    RAISE EXCEPTION
      'website-visible project_reports target not found: %/%/%',
      v_job.project_slug,
      v_job.report_type,
      COALESCE(v_job.locale, 'ko');
  END IF;

  WITH latest_visible_language_reports AS (
    SELECT DISTINCT ON (language) id
    FROM public.project_reports
    WHERE project_id = v_project_id
      AND report_type::text = v_job.report_type
      AND status IN ('published', 'coming_soon', 'in_review')
    ORDER BY language, version DESC, updated_at DESC NULLS LAST, id
  )
  UPDATE public.project_reports AS pr
  SET
    card_data =
      COALESCE(pr.card_data, '{}'::jsonb)
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
      ),
    marketing_content_by_lang = COALESCE(v_job.candidate_patch -> 'marketing_content_by_lang', pr.marketing_content_by_lang),
    summary_source_md_file_id = COALESCE(v_job.candidate_patch ->> 'summary_source_md_file_id', pr.summary_source_md_file_id),
    summary_source_md_name = COALESCE(v_job.candidate_patch ->> 'summary_source_md_name', pr.summary_source_md_name),
    summary_source_md_archived_url = COALESCE(v_job.candidate_patch ->> 'summary_source_md_archived_url', pr.summary_source_md_archived_url),
    summary_generated_at = COALESCE((v_job.candidate_patch ->> 'summary_generated_at')::timestamptz, pr.summary_generated_at),
    card_summary_ko = COALESCE(v_job.candidate_patch ->> 'card_summary_ko', pr.card_summary_ko),
    card_summary_en = COALESCE(v_job.candidate_patch ->> 'card_summary_en', pr.card_summary_en),
    card_summary_fr = COALESCE(v_job.candidate_patch ->> 'card_summary_fr', pr.card_summary_fr),
    card_summary_es = COALESCE(v_job.candidate_patch ->> 'card_summary_es', pr.card_summary_es),
    card_summary_de = COALESCE(v_job.candidate_patch ->> 'card_summary_de', pr.card_summary_de),
    card_summary_ja = COALESCE(v_job.candidate_patch ->> 'card_summary_ja', pr.card_summary_ja),
    card_summary_zh = COALESCE(v_job.candidate_patch ->> 'card_summary_zh', pr.card_summary_zh),
    risk_level = COALESCE(v_job.candidate_patch ->> 'risk_level', pr.risk_level),
    card_risk_score = COALESCE((v_job.candidate_patch ->> 'card_risk_score')::integer, pr.card_risk_score),
    updated_at = v_now
  FROM latest_visible_language_reports AS latest
  WHERE pr.id = latest.id;

  GET DIAGNOSTICS v_updated_report_count = ROW_COUNT;

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
    'candidate_version', v_candidate_version,
    'target_version', v_target.version,
    'updated_project_report_count', v_updated_report_count,
    'sibling_update_scope', 'latest_visible_per_language',
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
      'candidate_version', v_candidate_version,
      'target_version', v_target.version,
      'updated_project_report_count', v_updated_report_count,
      'sibling_update_scope', 'latest_visible_per_language',
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
    'candidate_version', v_candidate_version,
    'target_version', v_target.version,
    'updated_project_report_count', v_updated_report_count,
    'sibling_update_scope', 'latest_visible_per_language',
    'authority_state', 'promoted'
  );
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'active promotion lock exists';
END;
$$;

COMMENT ON FUNCTION public.promote_report_summary_job(uuid, text, text, text) IS
  'Atomically promotes a validation-passed report_summary_jobs row into the latest website-visible project_reports row for each language sibling, including version-skewed language rows.';
