-- Cancel stale AINFT MAT rows that were produced by the earlier Immutable
-- filename/OCR misclassification bug.
--
-- Immutable reports are now published against tracked_projects.slug =
-- 'immutable-x'. Any AINFT maturity row that still carries Immutable titles or
-- Immutable asset URLs is stale and must not remain website-visible.

UPDATE public.project_reports AS pr
SET
  status = 'cancelled'::report_status,
  is_latest = false,
  updated_at = now()
FROM public.tracked_projects AS tp
WHERE pr.project_id = tp.id
  AND tp.slug = 'ainft'
  AND pr.report_type = 'maturity'::report_type
  AND pr.status IN ('published', 'approved', 'in_review')
  AND (
    lower(COALESCE(pr.title_en, '')) LIKE '%immutable%'
    OR lower(COALESCE(pr.title_ko, '')) LIKE '%immutable%'
    OR lower(COALESCE(pr.title_ja, '')) LIKE '%immutable%'
    OR lower(COALESCE(pr.title_zh, '')) LIKE '%immutable%'
    OR lower(COALESCE(pr.gdrive_url, '')) LIKE '%immutable%'
    OR lower(COALESCE(pr.gdrive_urls_by_lang, '{}'::jsonb)::text) LIKE '%immutable%'
    OR lower(COALESCE(pr.file_urls_by_lang, '{}'::jsonb)::text) LIKE '%immutable%'
    OR lower(COALESCE(pr.slide_html_urls_by_lang, '{}'::jsonb)::text) LIKE '%immutable%'
  );
