DO $$
DECLARE
  v_job_id uuid := 'fabcc35f-0397-41fa-8621-432437d68441'::uuid;
  v_report_id uuid := '4d654e68-5355-4e56-8c24-99362e08338f'::uuid;
  v_report public.project_reports%ROWTYPE;
  v_now timestamptz := now();
BEGIN
  SELECT *
  INTO v_report
  FROM public.project_reports
  WHERE id = v_report_id
    AND report_type::text = 'forensic'
    AND language = 'en'
    AND version = 2
    AND status = 'published'
    AND card_data -> 'summary_authority' ->> 'job_id' = v_job_id::text
  LIMIT 1;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'expected repaired Decentraland FOR EN v2 report row not found';
  END IF;

  UPDATE public.project_reports
  SET
    card_data = COALESCE(card_data, '{}'::jsonb) || jsonb_build_object(
      'summary_authority',
      COALESCE(card_data -> 'summary_authority', '{}'::jsonb) || jsonb_build_object(
        'repair_issue', 'BCE-2129',
        'sibling_update_scope', 'latest_visible_per_language',
        'state_reconciled_at', v_now
      )
    ),
    updated_at = v_now
  WHERE id = v_report.id;

  UPDATE public.report_summary_jobs
  SET
    status = 'candidate_ready',
    validation_status = 'valid',
    validation_errors = '[]'::jsonb,
    authority_state = 'promoted',
    authority_mode = 'llm_active',
    promotion_decision = 'promote',
    promotion_decision_reason = 'validated candidate promoted to project_reports; BCE-2129 job state reconciled after latest-language sibling repair',
    promoted_project_report_id = COALESCE(promoted_project_report_id, '83cdd187-4203-44d9-b86e-117f3e16f6e3'::uuid),
    promoted_at = COALESCE(promoted_at, v_now),
    promotion_audit = COALESCE(promotion_audit, '{}'::jsonb) || jsonb_build_object(
      'state_reconcile_issue', 'BCE-2129',
      'state_reconcile_actor', 'github-actions:db-migration',
      'state_reconciled_at', v_now,
      'state_reconcile_reason', 'repaired EN v2 project_report row already carries the expected summary authority',
      'sibling_update_scope', 'latest_visible_per_language'
    ),
    updated_at = v_now
  WHERE id = v_job_id
    AND project_slug = 'decentraland'
    AND report_type = 'forensic';

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Decentraland FOR summary job not found for reconciliation';
  END IF;

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
    'summary_authority_gate.job_state_reconciled',
    'info',
    'Summary Authority Gate job state reconciled after latest-language sibling repair',
    jsonb_build_object(
      'pipeline', 'analysis-md-summary-candidate',
      'node', 'summary_authority_gate',
      'issue', 'BCE-2129',
      'job_id', v_job_id,
      'project_slug', 'decentraland',
      'report_type', 'forensic',
      'locale', 'ko',
      'project_report_id', v_report.id,
      'project_report_language', v_report.language,
      'project_report_version', v_report.version,
      'sibling_update_scope', 'latest_visible_per_language',
      'authority_mode', 'llm_active'
    ),
    v_now
  );
END;
$$;
