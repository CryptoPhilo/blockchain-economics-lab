-- Create the missing Arcium Korean forensic report shell required by the
-- Analysis Markdown Summary Authority Gate. The gate promotes validated
-- summary candidates into existing project/report rows; it must not create
-- those targets implicitly during promotion.

WITH target_project AS (
  SELECT id
  FROM public.tracked_projects
  WHERE slug = 'arcium'
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
  'Arcium Forensic Report',
  'Arcium 포렌식 분석 보고서',
  jsonb_build_object('ko', 'coming_soon'),
  '{}'::jsonb,
  '{}'::jsonb,
  '{}'::jsonb,
  jsonb_build_object(
    'report_type', 'forensic',
    'slug', 'arcium',
    'summary_authority_target', jsonb_build_object(
      'issue', 'BCE-2161',
      'blocked_issue', 'BCE-2160',
      'job_id', '0334ab47-dfa6-44ae-aa43-884fcb8d74ae',
      'source_identity', 'drive:1y_edFrd7AW9I0RwVU7BeTyGohj4uxWG-:0B8HYgThT3NBydHJ3cmdQYjFJUVBwK0hBVXVBVUpWelo4QkxBPQ',
      'drive_file_id', '1y_edFrd7AW9I0RwVU7BeTyGohj4uxWG-',
      'revision_id', '0B8HYgThT3NBydHJ3cmdQYjFJUVBwK0hBVXVBVUpWelo4QkxBPQ',
      'created_for', 'Summary Authority Gate target backfill'
    )
  ),
  true,
  'summary-authority-target:arcium/forensic/ko/version:1',
  'ARX 시장 무결성 및 심층 포렌식 리스크 보고서.md',
  now(),
  now()
FROM target_project
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
        'issue', 'BCE-2161',
        'blocked_issue', 'BCE-2160',
        'job_id', '0334ab47-dfa6-44ae-aa43-884fcb8d74ae',
        'source_identity', 'drive:1y_edFrd7AW9I0RwVU7BeTyGohj4uxWG-:0B8HYgThT3NBydHJ3cmdQYjFJUVBwK0hBVXVBVUpWelo4QkxBPQ',
        'drive_file_id', '1y_edFrd7AW9I0RwVU7BeTyGohj4uxWG-',
        'revision_id', '0B8HYgThT3NBydHJ3cmdQYjFJUVBwK0hBVXVBVUpWelo4QkxBPQ',
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
WHERE target_project.slug = 'arcium'
  AND report_target.project_id = target_project.id
  AND report_target.report_type::text = 'forensic'
  AND report_target.version = 1
  AND report_target.language = 'ko'
  AND report_target.status IN ('published', 'coming_soon', 'in_review');
