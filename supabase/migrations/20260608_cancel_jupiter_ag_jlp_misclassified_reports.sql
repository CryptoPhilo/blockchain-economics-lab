-- Cancel Jupiter Perps LP rows that were accidentally attached to
-- tracked_projects.slug = 'jupiter-ag' before JLP had an explicit runtime seed
-- and alias guard.
--
-- Correct JLP rows should be republished under tracked_projects.slug =
-- 'jupiter-perps-lp' by rerunning the slide pipeline after the guard lands.

WITH stale_reports AS (
  SELECT pr.id
  FROM public.project_reports AS pr
  JOIN public.tracked_projects AS tp ON tp.id = pr.project_id
  WHERE tp.slug = 'jupiter-ag'
    AND pr.report_type = 'econ'::report_type
    AND pr.status IN ('published', 'approved', 'in_review', 'coming_soon')
    AND (
      lower(COALESCE(pr.source_filename, '')) LIKE '%jupiter%perps%'
      OR lower(COALESCE(pr.source_filename, '')) LIKE '%jlp%'
      OR lower(COALESCE(pr.title_en, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.title_ko, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.title_fr, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.title_es, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.title_de, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.title_ja, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.title_zh, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.card_summary_en, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.card_summary_ko, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.card_summary_fr, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.card_summary_es, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.card_summary_de, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.card_summary_ja, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.card_summary_zh, '')) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.marketing_content_by_lang, '{}'::jsonb)::text) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.card_data, '{}'::jsonb)::text) LIKE '%jupiter perps%'
      OR lower(COALESCE(pr.gdrive_urls_by_lang, '{}'::jsonb)::text) LIKE '%jupiter%perps%'
      OR lower(COALESCE(pr.file_urls_by_lang, '{}'::jsonb)::text) LIKE '%jupiter%perps%'
      OR lower(COALESCE(pr.slide_html_urls_by_lang, '{}'::jsonb)::text) LIKE '%jupiter%perps%'
      OR lower(COALESCE(pr.cover_image_urls_by_lang, '{}'::jsonb)::text) LIKE '%jupiter%perps%'
      OR lower(COALESCE(pr.marketing_content_by_lang, '{}'::jsonb)::text) LIKE '%jlp%'
      OR lower(COALESCE(pr.card_data, '{}'::jsonb)::text) LIKE '%jlp%'
      OR lower(COALESCE(pr.gdrive_urls_by_lang, '{}'::jsonb)::text) LIKE '%jlp%'
      OR lower(COALESCE(pr.file_urls_by_lang, '{}'::jsonb)::text) LIKE '%jlp%'
      OR lower(COALESCE(pr.slide_html_urls_by_lang, '{}'::jsonb)::text) LIKE '%jlp%'
      OR lower(COALESCE(pr.cover_image_urls_by_lang, '{}'::jsonb)::text) LIKE '%jlp%'
    )
)
UPDATE public.project_reports AS pr
SET
  status = 'cancelled'::report_status,
  is_latest = false,
  updated_at = now()
FROM stale_reports
WHERE pr.id = stale_reports.id;

UPDATE public.tracked_projects AS tp
SET
  last_econ_report_at = (
    SELECT max(COALESCE(pr.published_at, pr.updated_at, pr.created_at))
    FROM public.project_reports AS pr
    WHERE pr.project_id = tp.id
      AND pr.report_type = 'econ'::report_type
      AND pr.status IN ('published', 'coming_soon')
  ),
  last_maturity_report_at = (
    SELECT max(COALESCE(pr.published_at, pr.updated_at, pr.created_at))
    FROM public.project_reports AS pr
    WHERE pr.project_id = tp.id
      AND pr.report_type = 'maturity'::report_type
      AND pr.status IN ('published', 'coming_soon')
  ),
  last_forensic_report_at = (
    SELECT max(COALESCE(pr.published_at, pr.updated_at, pr.created_at))
    FROM public.project_reports AS pr
    WHERE pr.project_id = tp.id
      AND pr.report_type = 'forensic'::report_type
      AND pr.status IN ('published', 'coming_soon')
  ),
  updated_at = now()
WHERE tp.slug = 'jupiter-ag';
