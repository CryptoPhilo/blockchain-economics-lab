-- Create the missing ZKsync Korean forensic report shell required by the
-- Analysis Markdown Summary Authority Gate. The gate promotes validated
-- summary candidates into existing project/report rows; it must not create
-- those targets implicitly during promotion.

WITH target_project AS (
  SELECT id
  FROM public.tracked_projects
  WHERE slug = 'zksync'
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
  'forensic',
  1,
  'coming_soon'::report_status,
  'ko',
  NULL,
  'ZKsync Forensic Report',
  'ZKsync 포렌식 리스크 분석 보고서',
  jsonb_build_object('ko', 'coming_soon'),
  '{}'::jsonb,
  '{}'::jsonb,
  '{}'::jsonb,
  jsonb_build_object(
    'report_type', 'forensic',
    'slug', 'zksync',
    'summary_authority_target', jsonb_build_object(
      'issue', 'BCE-2333',
      'blocked_issue', 'BCE-2332',
      'source_identity', 'drive:1PXLbDbDMMlCgkVhqOrEWUc2KQ9mDkynU:0B8HYgThT3NBybG5vL2NWWjFzNEpzNHlmZzQ5YWZGcVhqMllJPQ',
      'drive_file_id', '1PXLbDbDMMlCgkVhqOrEWUc2KQ9mDkynU',
      'revision_id', '0B8HYgThT3NBybG5vL2NWWjFzNEpzNHlmZzQ5YWZGcVhqMllJPQ',
      'source_sha256', '5a7fd51e1b957fe758ec04619c307a5a566e3ca5fd96958d464b7af1adbe5cd8',
      'created_for', 'Summary Authority Gate target backfill'
    )
  ),
  true,
  'summary-authority-target:zksync/forensic/ko/version:1',
  'ZK 시장 무결성 및 심층 포렌식 리스크 보고서.md',
  now(),
  now()
FROM target_project
WHERE NOT EXISTS (
  SELECT 1
  FROM public.project_reports existing
  WHERE existing.project_id = target_project.id
    AND existing.report_type::text = 'forensic'
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
        'issue', 'BCE-2333',
        'blocked_issue', 'BCE-2332',
        'source_identity', 'drive:1PXLbDbDMMlCgkVhqOrEWUc2KQ9mDkynU:0B8HYgThT3NBybG5vL2NWWjFzNEpzNHlmZzQ5YWZGcVhqMllJPQ',
        'drive_file_id', '1PXLbDbDMMlCgkVhqOrEWUc2KQ9mDkynU',
        'revision_id', '0B8HYgThT3NBybG5vL2NWWjFzNEpzNHlmZzQ5YWZGcVhqMllJPQ',
        'source_sha256', '5a7fd51e1b957fe758ec04619c307a5a566e3ca5fd96958d464b7af1adbe5cd8',
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
  last_forensic_report_at = COALESCE(
    target_project.last_forensic_report_at,
    report_target.updated_at,
    now()
  ),
  updated_at = now()
FROM public.project_reports report_target
WHERE target_project.slug = 'zksync'
  AND report_target.project_id = target_project.id
  AND report_target.report_type::text = 'forensic'
  AND report_target.version = 1
  AND report_target.language = 'ko'
  AND report_target.status IN ('published', 'coming_soon', 'in_review');
