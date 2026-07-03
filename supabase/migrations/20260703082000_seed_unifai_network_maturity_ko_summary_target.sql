-- Create the missing UnifAI Network Korean maturity report shell required by
-- the Analysis Markdown Summary Authority Gate. The gate promotes validated
-- summary candidates into existing project/report rows; it must not create
-- those targets implicitly during promotion.

WITH target_project AS (
  SELECT id
  FROM public.tracked_projects
  WHERE id = '68d8f5e2-5562-4ee3-bf52-cd9b4eb250c7'::uuid
    AND slug = 'unifai-network'
  LIMIT 1
)
INSERT INTO public.project_reports (
  project_id,
  report_type,
  version,
  status,
  language,
  published_at,
  title_en,
  title_ko,
  translation_status,
  file_urls_by_lang,
  gdrive_urls_by_lang,
  slide_html_urls_by_lang,
  card_data,
  is_latest,
  source_identity,
  source_filename,
  created_at,
  updated_at
)
SELECT
  target_project.id,
  'maturity',
  1,
  'coming_soon'::report_status,
  'ko',
  NULL,
  'UnifAI Network Maturity Report',
  'UnifAI Network 성숙도 평가 보고서',
  jsonb_build_object('ko', 'coming_soon'),
  '{}'::jsonb,
  '{}'::jsonb,
  '{}'::jsonb,
  jsonb_build_object(
    'report_type', 'maturity',
    'slug', 'unifai-network',
    'summary_authority_target', jsonb_build_object(
      'issue', 'BCE-2388',
      'blocked_issue', 'BCE-2387',
      'source_identity', 'drive:1SM22wbikyiNN-fkqCibzCI65CC-cdQpK:0B8HYgThT3NByMnVuNkl4alJZdVZBVmZsS2dUZ2FPRWpWRlFRPQ',
      'drive_file_id', '1SM22wbikyiNN-fkqCibzCI65CC-cdQpK',
      'revision_id', '0B8HYgThT3NByMnVuNkl4alJZdVZBVmZsS2dUZ2FPRWpWRlFRPQ',
      'source_sha256', '7496a28aa06f6921892c020e77e5288dec608f47c7667f4902585885eebf68f0',
      'created_for', 'Summary Authority Gate target backfill'
    )
  ),
  true,
  'summary-authority-target:unifai-network/maturity/ko/version:1',
  'UnifAI Network의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025 - 2026.md',
  now(),
  now()
FROM target_project
WHERE NOT EXISTS (
  SELECT 1
  FROM public.project_reports existing
  WHERE existing.project_id = target_project.id
    AND existing.report_type::text = 'maturity'
    AND existing.version = 1
    AND existing.language = 'ko'
)
ON CONFLICT (project_id, report_type, version, language) DO UPDATE
SET
  status = CASE
    WHEN public.project_reports.status = 'cancelled'::report_status
      THEN 'coming_soon'::report_status
    ELSE public.project_reports.status
  END,
  translation_status = CASE
    WHEN public.project_reports.status = 'cancelled'::report_status
      THEN COALESCE(public.project_reports.translation_status, '{}'::jsonb)
        || jsonb_build_object('ko', 'coming_soon')
    ELSE public.project_reports.translation_status
  END,
  card_data = COALESCE(public.project_reports.card_data, '{}'::jsonb)
    || jsonb_build_object(
      'summary_authority_target',
      jsonb_build_object(
        'issue', 'BCE-2388',
        'blocked_issue', 'BCE-2387',
        'source_identity', 'drive:1SM22wbikyiNN-fkqCibzCI65CC-cdQpK:0B8HYgThT3NByMnVuNkl4alJZdVZBVmZsS2dUZ2FPRWpWRlFRPQ',
        'drive_file_id', '1SM22wbikyiNN-fkqCibzCI65CC-cdQpK',
        'revision_id', '0B8HYgThT3NByMnVuNkl4alJZdVZBVmZsS2dUZ2FPRWpWRlFRPQ',
        'source_sha256', '7496a28aa06f6921892c020e77e5288dec608f47c7667f4902585885eebf68f0',
        'created_for', 'Summary Authority Gate target backfill'
      )
    ),
  is_latest = CASE
    WHEN public.project_reports.status = 'cancelled'::report_status THEN true
    ELSE public.project_reports.is_latest
  END,
  source_identity = COALESCE(
    public.project_reports.source_identity,
    EXCLUDED.source_identity
  ),
  source_filename = COALESCE(
    public.project_reports.source_filename,
    EXCLUDED.source_filename
  ),
  updated_at = now();

UPDATE public.tracked_projects target_project
SET
  last_maturity_report_at = COALESCE(
    target_project.last_maturity_report_at,
    report_target.updated_at,
    now()
  ),
  updated_at = now()
FROM public.project_reports report_target
WHERE target_project.id = '68d8f5e2-5562-4ee3-bf52-cd9b4eb250c7'::uuid
  AND target_project.slug = 'unifai-network'
  AND report_target.project_id = target_project.id
  AND report_target.report_type::text = 'maturity'
  AND report_target.version = 1
  AND report_target.language = 'ko'
  AND report_target.status IN ('published', 'coming_soon', 'in_review');
