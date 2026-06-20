-- Allow website reads for review-ready slide reports.
--
-- The app intentionally queries `in_review` reports that already have
-- generated slide HTML so restored pipeline output can appear on project pages
-- before the broader report lifecycle is normalized. Rows without slide HTML
-- remain hidden unless they are published or coming soon.

DROP POLICY IF EXISTS "Public can view published reports" ON public.project_reports;
DROP POLICY IF EXISTS "Public can view published and coming soon reports" ON public.project_reports;
DROP POLICY IF EXISTS "Public can view published coming soon and review-ready slide reports" ON public.project_reports;

CREATE POLICY "Public can view published coming soon and review-ready slide reports"
  ON public.project_reports
  FOR SELECT
  USING (
    status IN ('published', 'coming_soon')
    OR (
      status = 'in_review'
      AND slide_html_urls_by_lang IS NOT NULL
      AND slide_html_urls_by_lang <> '{}'::jsonb
    )
  );
