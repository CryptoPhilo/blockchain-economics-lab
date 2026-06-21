-- BCE-2033: create the missing Korean FOR target shell for AXS.
--
-- The Summary Authority Gate promotes a validation-passed Korean candidate into
-- a website-visible project_reports row for the same project/report/locale. AXS
-- currently has only a version-1 forensic English coming_soon shell, so the
-- gate correctly blocks on axie-infinity/forensic/ko. This migration seeds the
-- matching Korean shell without publishing a slide asset.

WITH target_project AS (
  SELECT id, name
  FROM public.tracked_projects
  WHERE slug = 'axie-infinity'
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
  file_url,
  page_count,
  task_id,
  product_id,
  title_en,
  title_ko,
  title_fr,
  title_es,
  title_de,
  title_ja,
  title_zh,
  translation_status,
  file_urls_by_lang,
  gdrive_file_id,
  gdrive_url,
  gdrive_download_url,
  gdrive_folder_id,
  gdrive_urls_by_lang,
  gdrive_url_free,
  card_keywords,
  card_summary_en,
  card_summary_ko,
  card_summary_fr,
  card_summary_es,
  card_summary_de,
  card_summary_ja,
  card_summary_zh,
  card_thumbnail_url,
  card_risk_score,
  card_data,
  card_qa_status,
  marketing_content_by_lang,
  previous_report_id,
  is_latest,
  whitepaper_revision_ref,
  slide_html_urls_by_lang,
  cover_image_urls_by_lang,
  summary_source_md_file_id,
  summary_source_md_name,
  summary_source_md_archived_url,
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
  sr.report_type,
  sr.version,
  sr.status,
  'ko',
  sr.assigned_to,
  sr.assigned_at,
  sr.started_at,
  sr.review_at,
  sr.approved_at,
  sr.published_at,
  sr.triggered_at,
  COALESCE(sr.trigger_reason, 'summary_authority_target_seed'),
  COALESCE(sr.trigger_data, '{}'::jsonb)
    || jsonb_build_object('seeded_by', 'BCE-2033', 'source_report_id', sr.id),
  sr.risk_level,
  sr.file_url,
  sr.page_count,
  sr.task_id,
  sr.product_id,
  sr.title_en,
  COALESCE(sr.title_ko, tp.name, 'Axie Infinity'),
  sr.title_fr,
  sr.title_es,
  sr.title_de,
  sr.title_ja,
  sr.title_zh,
  COALESCE(sr.translation_status, '{}'::jsonb) || jsonb_build_object('ko', sr.status::text),
  COALESCE(sr.file_urls_by_lang, '{}'::jsonb),
  sr.gdrive_file_id,
  sr.gdrive_url,
  sr.gdrive_download_url,
  sr.gdrive_folder_id,
  COALESCE(sr.gdrive_urls_by_lang, '{}'::jsonb),
  sr.gdrive_url_free,
  sr.card_keywords,
  sr.card_summary_en,
  sr.card_summary_ko,
  sr.card_summary_fr,
  sr.card_summary_es,
  sr.card_summary_de,
  sr.card_summary_ja,
  sr.card_summary_zh,
  sr.card_thumbnail_url,
  sr.card_risk_score,
  COALESCE(sr.card_data, '{}'::jsonb)
    || jsonb_build_object(
      'report_type', 'forensic',
      'slug', 'axie-infinity',
      'summary_authority_target_seed', jsonb_build_object(
        'issue', 'BCE-2033',
        'source_report_id', sr.id,
        'seeded_at', now()
      )
    ),
  sr.card_qa_status,
  COALESCE(sr.marketing_content_by_lang, '{}'::jsonb),
  NULL,
  true,
  sr.whitepaper_revision_ref,
  COALESCE(sr.slide_html_urls_by_lang, '{}'::jsonb),
  COALESCE(sr.cover_image_urls_by_lang, '{}'::jsonb),
  sr.summary_source_md_file_id,
  sr.summary_source_md_name,
  sr.summary_source_md_archived_url,
  sr.summary_generated_at,
  sr.source_file_id,
  sr.source_modified_time,
  sr.source_size,
  sr.source_checksum,
  sr.source_filename,
  now(),
  now()
FROM source_report sr
JOIN target_project tp ON tp.id = sr.project_id
ON CONFLICT (project_id, report_type, version, language) DO UPDATE
SET
  status = CASE
    WHEN public.project_reports.status IN ('published', 'coming_soon', 'in_review')
      THEN public.project_reports.status
    ELSE EXCLUDED.status
  END,
  title_ko = COALESCE(public.project_reports.title_ko, EXCLUDED.title_ko),
  translation_status = COALESCE(public.project_reports.translation_status, '{}'::jsonb)
    || jsonb_build_object('ko', COALESCE(public.project_reports.status, EXCLUDED.status)::text),
  card_data = COALESCE(public.project_reports.card_data, '{}'::jsonb)
    || jsonb_build_object(
      'summary_authority_target_seed',
      jsonb_build_object(
        'issue', 'BCE-2033',
        'refreshed_at', now()
      )
    ),
  is_latest = true,
  updated_at = now();
