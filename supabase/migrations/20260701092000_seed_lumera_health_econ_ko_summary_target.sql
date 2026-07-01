-- Create the missing Lumera Health Korean ECON report shell required by the
-- Analysis Markdown Summary Authority Gate. The gate promotes validated
-- summary candidates into existing project/report rows; it must not create
-- those targets implicitly during promotion.

WITH target_project AS (
  SELECT id
  FROM public.tracked_projects
  WHERE slug = 'lumera-health'
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
  'econ',
  1,
  'coming_soon'::report_status,
  'ko',
  NULL,
  'Lumera Health Economic Design Report',
  'Lumera Health 크립토이코노미 설계 분석 보고서',
  jsonb_build_object('ko', 'coming_soon'),
  '{}'::jsonb,
  '{}'::jsonb,
  '{}'::jsonb,
  jsonb_build_object(
    'report_type', 'econ',
    'slug', 'lumera-health',
    'summary_authority_target', jsonb_build_object(
      'issue', 'BCE-2345',
      'blocked_issue', 'BCE-2344',
      'job_id', '79dbd466-7414-4feb-b399-d6e51b1fad8d',
      'source_identity', 'drive:1_tlzgWm0WENZFUNywasOjgI9zxr9V0Uo:0B8HYgThT3NBydG5YRzc5dFdmRVZ6WEpGSEw0VGs4M0pySG40PQ',
      'drive_file_id', '1_tlzgWm0WENZFUNywasOjgI9zxr9V0Uo',
      'revision_id', '0B8HYgThT3NBydG5YRzc5dFdmRVZ6WEpGSEw0VGs4M0pySG40PQ',
      'source_sha256', '65e6313446894be3be5ec7254fb820c35e5f1201f39039069899c47fc97761f3',
      'created_for', 'Summary Authority Gate target backfill'
    )
  ),
  true,
  'summary-authority-target:lumera-health/econ/ko/version:1',
  'Lumera Health 크립토 이코노미 설계 분석 보고서.md',
  now(),
  now()
FROM target_project
WHERE NOT EXISTS (
  SELECT 1
  FROM public.project_reports existing
  WHERE existing.project_id = target_project.id
    AND existing.report_type::text = 'econ'
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
        'issue', 'BCE-2345',
        'blocked_issue', 'BCE-2344',
        'job_id', '79dbd466-7414-4feb-b399-d6e51b1fad8d',
        'source_identity', 'drive:1_tlzgWm0WENZFUNywasOjgI9zxr9V0Uo:0B8HYgThT3NBydG5YRzc5dFdmRVZ6WEpGSEw0VGs4M0pySG40PQ',
        'drive_file_id', '1_tlzgWm0WENZFUNywasOjgI9zxr9V0Uo',
        'revision_id', '0B8HYgThT3NBydG5YRzc5dFdmRVZ6WEpGSEw0VGs4M0pySG40PQ',
        'source_sha256', '65e6313446894be3be5ec7254fb820c35e5f1201f39039069899c47fc97761f3',
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
  last_econ_report_at = COALESCE(
    target_project.last_econ_report_at,
    report_target.updated_at,
    now()
  ),
  updated_at = now()
FROM public.project_reports report_target
WHERE target_project.slug = 'lumera-health'
  AND report_target.project_id = target_project.id
  AND report_target.report_type::text = 'econ'
  AND report_target.version = 1
  AND report_target.language = 'ko'
  AND report_target.status IN ('published', 'coming_soon', 'in_review');
