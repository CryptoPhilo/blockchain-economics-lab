-- BCE: Normalize slide-backed report rows to published.
--
-- The active report pipelines define Google Drive Slide/{TYPE} PDF presence as
-- the publication trigger. Older pipeline code wrote asset-backed rows as
-- `in_review`, which hid ECON/MAT/FOR badges on the website. This trigger is a
-- final database guard: if stale code writes a slide/GDrive-backed report as
-- `in_review`, the database stores it as `published` instead.

CREATE OR REPLACE FUNCTION public.normalize_slide_report_publication_status()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.status = 'in_review'::report_status
     AND (
       (NEW.slide_html_urls_by_lang IS NOT NULL AND NEW.slide_html_urls_by_lang <> '{}'::jsonb)
       OR (NEW.gdrive_urls_by_lang IS NOT NULL AND NEW.gdrive_urls_by_lang <> '{}'::jsonb)
       OR NULLIF(NEW.gdrive_url, '') IS NOT NULL
       OR NULLIF(NEW.file_url, '') IS NOT NULL
     )
  THEN
    NEW.status := 'published'::report_status;
    NEW.review_at := NULL;
    NEW.published_at := COALESCE(NEW.published_at, NEW.updated_at, NEW.created_at, now());
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS normalize_slide_report_publication_status_on_project_reports
  ON public.project_reports;

CREATE TRIGGER normalize_slide_report_publication_status_on_project_reports
  BEFORE INSERT OR UPDATE OF status, slide_html_urls_by_lang, gdrive_urls_by_lang, gdrive_url, file_url
  ON public.project_reports
  FOR EACH ROW
  EXECUTE FUNCTION public.normalize_slide_report_publication_status();

UPDATE public.project_reports
SET
  status = 'published'::report_status,
  review_at = NULL,
  published_at = COALESCE(published_at, updated_at, created_at, now()),
  updated_at = now()
WHERE status = 'in_review'::report_status
  AND (
    (slide_html_urls_by_lang IS NOT NULL AND slide_html_urls_by_lang <> '{}'::jsonb)
    OR (gdrive_urls_by_lang IS NOT NULL AND gdrive_urls_by_lang <> '{}'::jsonb)
    OR NULLIF(gdrive_url, '') IS NOT NULL
    OR NULLIF(file_url, '') IS NOT NULL
  );
