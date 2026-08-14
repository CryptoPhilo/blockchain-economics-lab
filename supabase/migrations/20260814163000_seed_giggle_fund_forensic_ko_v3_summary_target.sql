-- Create the missing Giggle Fund Korean forensic v3 report shell required by
-- the Analysis Markdown Summary Authority Gate. The gate promotes validated
-- summary candidates into existing website-visible project_reports rows; it
-- must not create report targets implicitly or fall back across versions.

UPDATE public.project_reports
SET
  is_latest = false,
  updated_at = now()
WHERE project_id = '735eaaa7-6ec9-445c-84be-cd7bfa31dfa2'::uuid
  AND report_type::text = 'forensic'
  AND language = 'ko'
  AND version < 3
  AND is_latest = true
  AND EXISTS (
    SELECT 1
    FROM public.tracked_projects target_project
    WHERE target_project.id = public.project_reports.project_id
      AND target_project.slug = 'giggle-fund'
      AND target_project.symbol = 'GIGGLE'
  );

WITH target_project AS (
  SELECT id
  FROM public.tracked_projects
  WHERE id = '735eaaa7-6ec9-445c-84be-cd7bfa31dfa2'::uuid
    AND slug = 'giggle-fund'
    AND symbol = 'GIGGLE'
  LIMIT 1
),
previous_ko AS (
  SELECT id, updated_at, published_at
  FROM public.project_reports
  WHERE project_id = '735eaaa7-6ec9-445c-84be-cd7bfa31dfa2'::uuid
    AND report_type::text = 'forensic'
    AND language = 'ko'
    AND version = 2
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
  previous_report_id,
  source_identity,
  source_filename,
  created_at,
  updated_at
)
SELECT
  target_project.id,
  'forensic',
  3,
  'coming_soon'::report_status,
  'ko',
  NULL,
  'Giggle Fund Forensic Risk Report',
  'Giggle Fund 포렌식 리스크 보고서',
  jsonb_build_object('ko', 'coming_soon'),
  '{}'::jsonb,
  '{}'::jsonb,
  '{}'::jsonb,
  jsonb_build_object(
    'report_type', 'forensic',
    'slug', 'giggle-fund',
    'source_md', jsonb_build_object(
      'name', 'giggle-fund_for_v3_ko.md',
      'slug', 'giggle-fund',
      'version', 3,
      'language', 'ko',
      'report_type', 'for',
      'drive_file_id', '1K0Rw-_D4Vx1cc21AeVaF70exANVPyEK6',
      'revision_id', '0B8HYgThT3NByVzYyRElmNVhMV3dRcm16NVRwYnBsOUdnUEFFPQ',
      'source_identity', 'drive:1K0Rw-_D4Vx1cc21AeVaF70exANVPyEK6:0B8HYgThT3NByVzYyRElmNVhMV3dRcm16NVRwYnBsOUdnUEFFPQ',
      'source_sha256', '948bda36fb5e7816ec4660ec99dd8d66e668ee2e0af761c86c4122efeace0a1d',
      'source_folder', 'analysis2/FOR',
      'web_view_link', 'https://drive.google.com/file/d/1K0Rw-_D4Vx1cc21AeVaF70exANVPyEK6/view?usp=drivesdk'
    ),
    'summary_authority_target', jsonb_build_object(
      'issue', 'BCE-3120',
      'blocked_issue', 'BCE-3119',
      'candidate_job_id', '4fa64f93-27b9-475f-957f-832e2e7b5f63',
      'source_identity', 'drive:1K0Rw-_D4Vx1cc21AeVaF70exANVPyEK6:0B8HYgThT3NByVzYyRElmNVhMV3dRcm16NVRwYnBsOUdnUEFFPQ',
      'drive_file_id', '1K0Rw-_D4Vx1cc21AeVaF70exANVPyEK6',
      'revision_id', '0B8HYgThT3NByVzYyRElmNVhMV3dRcm16NVRwYnBsOUdnUEFFPQ',
      'source_sha256', '948bda36fb5e7816ec4660ec99dd8d66e668ee2e0af761c86c4122efeace0a1d',
      'created_for', 'Summary Authority Gate target backfill'
    )
  ),
  true,
  previous_ko.id,
  'summary-authority-target:giggle-fund/forensic/ko/version:3',
  'giggle-fund_for_v3_ko.md',
  now(),
  now()
FROM target_project
LEFT JOIN previous_ko ON true
WHERE NOT EXISTS (
  SELECT 1
  FROM public.project_reports existing
  WHERE existing.project_id = target_project.id
    AND existing.report_type::text = 'forensic'
    AND existing.version = 3
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
        'issue', 'BCE-3120',
        'blocked_issue', 'BCE-3119',
        'candidate_job_id', '4fa64f93-27b9-475f-957f-832e2e7b5f63',
        'source_identity', 'drive:1K0Rw-_D4Vx1cc21AeVaF70exANVPyEK6:0B8HYgThT3NByVzYyRElmNVhMV3dRcm16NVRwYnBsOUdnUEFFPQ',
        'drive_file_id', '1K0Rw-_D4Vx1cc21AeVaF70exANVPyEK6',
        'revision_id', '0B8HYgThT3NByVzYyRElmNVhMV3dRcm16NVRwYnBsOUdnUEFFPQ',
        'source_sha256', '948bda36fb5e7816ec4660ec99dd8d66e668ee2e0af761c86c4122efeace0a1d',
        'created_for', 'Summary Authority Gate target backfill'
      )
    ),
  is_latest = true,
  previous_report_id = COALESCE(public.project_reports.previous_report_id, EXCLUDED.previous_report_id),
  source_identity = COALESCE(public.project_reports.source_identity, EXCLUDED.source_identity),
  source_filename = COALESCE(public.project_reports.source_filename, EXCLUDED.source_filename),
  updated_at = now();

UPDATE public.tracked_projects target_project
SET
  last_forensic_report_at = COALESCE(
    report_target.published_at,
    report_target.updated_at,
    target_project.last_forensic_report_at,
    now()
  ),
  updated_at = now()
FROM public.project_reports report_target
WHERE target_project.id = '735eaaa7-6ec9-445c-84be-cd7bfa31dfa2'::uuid
  AND target_project.slug = 'giggle-fund'
  AND target_project.symbol = 'GIGGLE'
  AND report_target.project_id = target_project.id
  AND report_target.report_type::text = 'forensic'
  AND report_target.version = 3
  AND report_target.language = 'ko'
  AND report_target.status IN ('published', 'coming_soon', 'in_review');
