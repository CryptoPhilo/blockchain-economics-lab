-- Cancel Ondo USDY ECON/MAT rows that were accidentally attached to
-- tracked_projects.slug = 'ondo-finance' before Ondo US Dollar Yield had an
-- explicit runtime seed and alias guard.
--
-- Correct USDY rows are now published under tracked_projects.slug =
-- 'ondo-us-dollar-yield'. The stale Ondo Finance rows leak into the homepage
-- showcase and detail routes because they still look like published reports.

WITH stale_reports AS (
  SELECT pr.id
  FROM public.project_reports AS pr
  JOIN public.tracked_projects AS tp ON tp.id = pr.project_id
  WHERE tp.slug = 'ondo-finance'
    AND pr.report_type IN ('econ'::report_type, 'maturity'::report_type)
    AND pr.status IN ('published', 'approved', 'in_review', 'coming_soon')
    AND (
      lower(COALESCE(pr.source_filename, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.title_en, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.title_ko, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.title_fr, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.title_es, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.title_de, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.title_ja, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.title_zh, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.card_summary_en, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.card_summary_ko, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.card_summary_fr, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.card_summary_es, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.card_summary_de, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.card_summary_ja, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.card_summary_zh, '')) LIKE '%usdy%'
      OR lower(COALESCE(pr.marketing_content_by_lang, '{}'::jsonb)::text) LIKE '%usdy%'
      OR lower(COALESCE(pr.card_data, '{}'::jsonb)::text) LIKE '%usdy%'
      OR lower(COALESCE(pr.gdrive_urls_by_lang, '{}'::jsonb)::text) LIKE '%usdy%'
      OR lower(COALESCE(pr.file_urls_by_lang, '{}'::jsonb)::text) LIKE '%usdy%'
      OR lower(COALESCE(pr.slide_html_urls_by_lang, '{}'::jsonb)::text) LIKE '%usdy%'
      OR lower(COALESCE(pr.cover_image_urls_by_lang, '{}'::jsonb)::text) LIKE '%usdy%'
      OR lower(COALESCE(pr.title_en, '')) LIKE '%ondo us dollar yield%'
      OR lower(COALESCE(pr.title_ko, '')) LIKE '%ondo us dollar yield%'
      OR lower(COALESCE(pr.card_summary_en, '')) LIKE '%ondo us dollar yield%'
      OR lower(COALESCE(pr.card_summary_ko, '')) LIKE '%ondo us dollar yield%'
      OR lower(COALESCE(pr.marketing_content_by_lang, '{}'::jsonb)::text) LIKE '%ondo us dollar yield%'
      OR lower(COALESCE(pr.card_data, '{}'::jsonb)::text) LIKE '%ondo us dollar yield%'
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
  updated_at = now()
WHERE tp.slug = 'ondo-finance';
