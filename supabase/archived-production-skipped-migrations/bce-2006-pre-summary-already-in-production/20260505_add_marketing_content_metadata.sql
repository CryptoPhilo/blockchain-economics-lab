-- BCE-1791: Marketing and website-summary content metadata.
--
-- Korean Markdown reports are the source of truth for website summaries and
-- marketing snippets. These columns store the derived multilingual marketing
-- copy plus the source Markdown provenance used to generate it.

ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS marketing_content_by_lang jsonb DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS summary_source_md_file_id text,
  ADD COLUMN IF NOT EXISTS summary_source_md_name text,
  ADD COLUMN IF NOT EXISTS summary_source_md_archived_url text,
  ADD COLUMN IF NOT EXISTS summary_generated_at timestamptz;

COMMENT ON COLUMN public.project_reports.marketing_content_by_lang IS
  'Per-language marketing copy derived from the Korean Markdown source. Shape: {"<lang>": "<~100 words>"}';

COMMENT ON COLUMN public.project_reports.summary_source_md_file_id IS
  'Google Drive file id of the Korean Markdown source used for summaries and marketing copy.';

COMMENT ON COLUMN public.project_reports.summary_source_md_archived_url IS
  'Google Drive web URL for the archived/copied Markdown source, when BCE_MARKETING_ARCHIVE_FOLDER_ID is configured.';
