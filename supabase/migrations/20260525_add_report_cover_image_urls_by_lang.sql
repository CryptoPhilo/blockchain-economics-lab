-- Store generated report cover image URLs per locale.
-- These are concrete Storage object URLs, not inferred from slide HTML paths.

ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS cover_image_urls_by_lang jsonb;

COMMENT ON COLUMN public.project_reports.cover_image_urls_by_lang IS
  'Locale keyed public cover image URLs extracted from slide HTML first-page images.';
