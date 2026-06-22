-- BCE-2059: create the missing Korean ECON target shell for SuperFortune.
--
-- The Summary Authority Gate promotes a validation-passed Korean candidate into
-- an existing website-visible project_reports row for the same project/report/
-- locale. SuperFortune previously had only a forensic English coming_soon
-- shell, so the gate correctly blocked on superfortune/econ/ko. This migration
-- seeds the matching Korean ECON shell and marks it published with the
-- summary-authority HTML artifact used by the website detail page.

WITH target_project AS (
  SELECT id, name
  FROM public.tracked_projects
  WHERE slug = 'superfortune'
  LIMIT 1
),
source_report AS (
  SELECT pr.*
  FROM public.project_reports pr
  JOIN target_project tp ON tp.id = pr.project_id
  WHERE pr.report_type::text = 'forensic'
    AND pr.language = 'en'
    AND pr.version = 1
    AND pr.status IN ('published', 'coming_soon', 'in_review')
  ORDER BY pr.updated_at DESC NULLS LAST, pr.created_at DESC NULLS LAST
  LIMIT 1
),
publication AS (
  SELECT
    '2026-06-21T01:55:34.644898+00:00'::timestamptz AS published_at,
    'https://wbqponoiyoeqlepxogcb.supabase.co/storage/v1/object/public/slides/econ/superfortune/v1/ko.html'::text AS slide_html_url
)
INSERT INTO public.project_reports (
  project_id,
  report_type,
  version,
  status,
  language,
  assigned_to,
  assigned_at,
  started_at,
  review_at,
  approved_at,
  published_at,
  triggered_at,
  trigger_reason,
  trigger_data,
  risk_level,
  page_count,
  task_id,
  product_id,
  title_en,
  title_ko,
  translation_status,
  file_urls_by_lang,
  gdrive_urls_by_lang,
  card_keywords,
  card_thumbnail_url,
  card_risk_score,
  card_data,
  card_qa_status,
  marketing_content_by_lang,
  previous_report_id,
  is_latest,
  slide_html_urls_by_lang,
  cover_image_urls_by_lang,
  summary_source_md_file_id,
  summary_source_md_name,
  summary_generated_at,
  source_file_id,
  source_modified_time,
  source_size,
  source_checksum,
  source_filename,
  created_at,
  updated_at
)
SELECT
  sr.project_id,
  'econ'::report_type,
  1,
  'published',
  'ko',
  sr.assigned_to,
  sr.assigned_at,
  sr.started_at,
  sr.review_at,
  COALESCE(sr.approved_at, publication.published_at),
  publication.published_at,
  sr.triggered_at,
  'summary_authority_target_seed',
  COALESCE(sr.trigger_data, '{}'::jsonb)
    || jsonb_build_object('seeded_by', 'BCE-2059', 'source_report_id', sr.id),
  sr.risk_level,
  sr.page_count,
  sr.task_id,
  sr.product_id,
  tp.name || ' Cryptoeconomic Analysis',
  tp.name || ' 크립토이코노미 분석',
  COALESCE(sr.translation_status, '{}'::jsonb) || jsonb_build_object('ko', 'published'),
  COALESCE(sr.file_urls_by_lang, '{}'::jsonb),
  COALESCE(sr.gdrive_urls_by_lang, '{}'::jsonb),
  sr.card_keywords,
  sr.card_thumbnail_url,
  sr.card_risk_score,
  COALESCE(sr.card_data, '{}'::jsonb)
    || jsonb_build_object(
      'report_type', 'econ',
      'slug', 'superfortune',
      'summary_authority_publication', jsonb_build_object(
        'issue', 'BCE-2059',
        'published_at', publication.published_at,
        'slide_html_url', publication.slide_html_url
      ),
      'summary_authority_target_seed', jsonb_build_object(
        'issue', 'BCE-2059',
        'source_report_id', sr.id,
        'seeded_at', publication.published_at
      )
    ),
  sr.card_qa_status,
  COALESCE(sr.marketing_content_by_lang, '{}'::jsonb),
  NULL,
  true,
  COALESCE(sr.slide_html_urls_by_lang, '{}'::jsonb)
    || jsonb_build_object('ko', publication.slide_html_url),
  COALESCE(sr.cover_image_urls_by_lang, '{}'::jsonb),
  '19EFm5tk1Iz2WMcGgZ_r5S8edlJMP2ErM',
  'SuperFortune 크립토이코노미 설계 분석 보고서.md',
  NULL,
  sr.source_file_id,
  sr.source_modified_time,
  sr.source_size,
  sr.source_checksum,
  sr.source_filename,
  publication.published_at,
  publication.published_at
FROM source_report sr
JOIN target_project tp ON tp.id = sr.project_id
JOIN publication ON true
ON CONFLICT (project_id, report_type, version, language) DO UPDATE
SET
  status = 'published',
  approved_at = COALESCE(public.project_reports.approved_at, EXCLUDED.approved_at),
  published_at = COALESCE(public.project_reports.published_at, EXCLUDED.published_at),
  title_ko = COALESCE(public.project_reports.title_ko, EXCLUDED.title_ko),
  translation_status = COALESCE(public.project_reports.translation_status, '{}'::jsonb)
    || jsonb_build_object('ko', 'published'),
  slide_html_urls_by_lang = COALESCE(public.project_reports.slide_html_urls_by_lang, '{}'::jsonb)
    || EXCLUDED.slide_html_urls_by_lang,
  card_data = COALESCE(public.project_reports.card_data, '{}'::jsonb)
    || jsonb_build_object(
      'summary_authority_publication',
      jsonb_build_object(
        'issue', 'BCE-2059',
        'published_at', COALESCE(public.project_reports.published_at, EXCLUDED.published_at),
        'slide_html_url', EXCLUDED.slide_html_urls_by_lang ->> 'ko'
      ),
      'summary_authority_target_seed',
      jsonb_build_object(
        'issue', 'BCE-2059',
        'refreshed_at', now()
      )
    ),
  is_latest = true,
  updated_at = now();

UPDATE public.tracked_projects
SET
  last_econ_report_at = COALESCE(last_econ_report_at, '2026-06-21T01:55:34.644898+00:00'::timestamptz),
  updated_at = now()
WHERE slug = 'superfortune';
