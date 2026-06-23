DO $$
DECLARE
  v_job public.report_summary_jobs%ROWTYPE;
  v_project_id uuid;
  v_now timestamptz := now();
  v_updated_report_count integer := 0;
BEGIN
  SELECT *
  INTO v_job
  FROM public.report_summary_jobs
  WHERE id = 'fabcc35f-0397-41fa-8621-432437d68441'::uuid
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Decentraland FOR summary job not found';
  END IF;

  IF v_job.project_slug <> 'decentraland'
     OR v_job.report_type <> 'forensic'
     OR COALESCE(v_job.validation_status, 'valid') <> 'valid'
     OR v_job.authority_state <> 'promoted' THEN
    RAISE EXCEPTION
      'unexpected Decentraland FOR job state: slug=% type=% validation=% authority=%',
      v_job.project_slug,
      v_job.report_type,
      v_job.validation_status,
      v_job.authority_state;
  END IF;

  SELECT id
  INTO v_project_id
  FROM public.tracked_projects
  WHERE slug = 'decentraland'
  LIMIT 1;

  IF v_project_id IS NULL THEN
    RAISE EXCEPTION 'tracked project not found: decentraland';
  END IF;

  WITH latest_visible_language_reports AS (
    SELECT DISTINCT ON (language) id
    FROM public.project_reports
    WHERE project_id = v_project_id
      AND report_type::text = 'forensic'
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
          'promoted_at', v_now,
          'repair_issue', 'BCE-2129',
          'sibling_update_scope', 'latest_visible_per_language'
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

  IF v_updated_report_count = 0 THEN
    RAISE EXCEPTION 'Decentraland FOR repair updated zero project_reports rows';
  END IF;

  UPDATE public.report_summary_jobs
  SET
    promotion_audit = COALESCE(promotion_audit, '{}'::jsonb) || jsonb_build_object(
      'repair_issue', 'BCE-2129',
      'repair_actor', 'github-actions:db-migration',
      'repair_reason', 'repair already-promoted job after latest-language sibling RPC migration',
      'repair_updated_project_report_count', v_updated_report_count,
      'updated_project_report_count', v_updated_report_count,
      'sibling_update_scope', 'latest_visible_per_language',
      'repaired_at', v_now
    ),
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
    'summary_authority_gate.repaired',
    'info',
    'Summary Authority Gate repaired latest visible language sibling rows',
    jsonb_build_object(
      'pipeline', 'analysis-md-summary-candidate',
      'node', 'summary_authority_gate',
      'issue', 'BCE-2129',
      'job_id', v_job.id,
      'project_slug', v_job.project_slug,
      'report_type', v_job.report_type,
      'locale', COALESCE(v_job.locale, 'ko'),
      'updated_project_report_count', v_updated_report_count,
      'sibling_update_scope', 'latest_visible_per_language',
      'authority_mode', 'llm_active'
    ),
    v_now
  );

  RAISE NOTICE
    'BCE-2129 repaired Decentraland FOR job %, updated % latest visible language rows',
    v_job.id,
    v_updated_report_count;
END;
$$;
