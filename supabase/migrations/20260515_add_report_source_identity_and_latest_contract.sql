-- BCE-1907: versioned Drive source identity and latest/default report contract.
--
-- The slide watcher must create a new project_reports version when a new
-- Google Drive PDF arrives for an existing (project_id, report_type, language)
-- group, while reprocessing the same Drive source remains idempotent.

ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS source_identity text,
  ADD COLUMN IF NOT EXISTS source_file_id text,
  ADD COLUMN IF NOT EXISTS source_modified_time text,
  ADD COLUMN IF NOT EXISTS source_size bigint,
  ADD COLUMN IF NOT EXISTS source_checksum text,
  ADD COLUMN IF NOT EXISTS source_filename text;

COMMENT ON COLUMN public.project_reports.source_identity IS
  'Stable Drive source identity used by the slide watcher for idempotent report version ingestion. Includes canonical project/type/language plus Drive file metadata.';
COMMENT ON COLUMN public.project_reports.source_file_id IS
  'Google Drive file id that produced this report version.';
COMMENT ON COLUMN public.project_reports.source_modified_time IS
  'Google Drive modifiedTime observed when this report version was ingested.';
COMMENT ON COLUMN public.project_reports.source_size IS
  'Google Drive file size observed when this report version was ingested.';
COMMENT ON COLUMN public.project_reports.source_checksum IS
  'Optional source checksum when available from Drive or a local hash.';
COMMENT ON COLUMN public.project_reports.source_filename IS
  'Google Drive filename observed when this report version was ingested.';

UPDATE public.project_reports
SET
  source_file_id = COALESCE(source_file_id, gdrive_file_id),
  source_identity = COALESCE(
    source_identity,
    concat_ws(
      '|',
      'legacy-gdrive',
      project_id::text,
      report_type::text,
      language,
      gdrive_file_id,
      'version:' || version::text
    )
  )
WHERE gdrive_file_id IS NOT NULL;

WITH ranked AS (
  SELECT
    id,
    row_number() OVER (
      PARTITION BY project_id, report_type, language
      ORDER BY
        CASE WHEN status IN ('published', 'approved', 'in_review', 'coming_soon') THEN 0 ELSE 1 END,
        version DESC,
        COALESCE(published_at, updated_at, created_at) DESC NULLS LAST,
        id DESC
    ) AS rn
  FROM public.project_reports
)
UPDATE public.project_reports pr
SET is_latest = (ranked.rn = 1)
FROM ranked
WHERE ranked.id = pr.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_project_reports_unique_source_identity
  ON public.project_reports (source_identity)
  WHERE source_identity IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_project_reports_one_latest_per_locale
  ON public.project_reports (project_id, report_type, language)
  WHERE is_latest = true;

CREATE INDEX IF NOT EXISTS idx_project_reports_source_file
  ON public.project_reports (source_file_id)
  WHERE source_file_id IS NOT NULL;
