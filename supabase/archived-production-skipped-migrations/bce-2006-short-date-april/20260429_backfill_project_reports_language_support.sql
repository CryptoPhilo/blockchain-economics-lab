-- BCE-1704: Backfill project_reports schema drift between production DB and git.
--
-- Production DB (wbqponoiyoeqlepxogcb) has columns/indexes that were applied via
-- earlier migrations (20260408182202 add_language_support_to_project_reports,
-- 20260409020850 add_gdrive_url_columns_and_rpc, 20260412030614 add_freemium_and_score_columns,
-- 20260414062525 add_for_card_and_email_leads, 20260416022513 add_report_version_chain_and_views,
-- 20260422234642 add_card_summary_multilingual_columns) but the corresponding migration files
-- were never committed to supabase/migrations/. This file backfills the project_reports portion
-- of that drift idempotently so fresh environments (staging, dev) reach the same schema.
--
-- Scope: project_reports columns + indexes only. Views/RPCs/other-table drift are out of scope
-- and tracked in BCE-1704 follow-ups.
--
-- Idempotent: every statement uses IF NOT EXISTS. Re-running this against production is a no-op.

-- 1. Language support (originally 20260408182202_add_language_support_to_project_reports)
ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS language text NOT NULL DEFAULT 'en';

ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS title_en text,
  ADD COLUMN IF NOT EXISTS title_ko text,
  ADD COLUMN IF NOT EXISTS title_fr text,
  ADD COLUMN IF NOT EXISTS title_es text,
  ADD COLUMN IF NOT EXISTS title_de text,
  ADD COLUMN IF NOT EXISTS title_ja text,
  ADD COLUMN IF NOT EXISTS title_zh text;

ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS translation_status jsonb
    DEFAULT '{"en":"pending","ko":"pending","fr":"pending","es":"pending","de":"pending","ja":"pending","zh":"pending"}'::jsonb;

ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS file_urls_by_lang jsonb DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_project_reports_language
  ON public.project_reports (language);

CREATE UNIQUE INDEX IF NOT EXISTS idx_project_reports_unique_version
  ON public.project_reports (project_id, report_type, version, language);

-- 2. Google Drive URL columns (originally 20260409020850_add_gdrive_url_columns_and_rpc)
ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS gdrive_file_id text,
  ADD COLUMN IF NOT EXISTS gdrive_url text,
  ADD COLUMN IF NOT EXISTS gdrive_download_url text,
  ADD COLUMN IF NOT EXISTS gdrive_folder_id text,
  ADD COLUMN IF NOT EXISTS gdrive_urls_by_lang jsonb DEFAULT '{}'::jsonb;

-- 3. Free-tier GDrive URL (originally 20260412030614_add_freemium_and_score_columns)
ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS gdrive_url_free text;

-- 4. FOR card metadata (originally 20260414062525_add_for_card_and_email_leads)
ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS card_keywords text[],
  ADD COLUMN IF NOT EXISTS card_summary_en text,
  ADD COLUMN IF NOT EXISTS card_summary_ko text,
  ADD COLUMN IF NOT EXISTS card_thumbnail_url text,
  ADD COLUMN IF NOT EXISTS card_risk_score integer,
  ADD COLUMN IF NOT EXISTS card_data jsonb,
  ADD COLUMN IF NOT EXISTS card_qa_status text DEFAULT 'pending';

-- 5. Version chain (originally 20260416022513_add_report_version_chain_and_views)
ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS previous_report_id uuid REFERENCES public.project_reports(id),
  ADD COLUMN IF NOT EXISTS is_latest boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS whitepaper_revision_ref text;

COMMENT ON COLUMN public.project_reports.previous_report_id IS
  'Links to the previous version of this report (same project_id, report_type, language)';
COMMENT ON COLUMN public.project_reports.is_latest IS
  'True if this is the most recent version for its (project_id, report_type, language) group';
COMMENT ON COLUMN public.project_reports.whitepaper_revision_ref IS
  'For ECON reports: reference to the whitepaper revision that triggered this report version';

CREATE INDEX IF NOT EXISTS idx_project_reports_latest
  ON public.project_reports (project_id, report_type, language)
  WHERE is_latest = true;

CREATE INDEX IF NOT EXISTS idx_project_reports_previous
  ON public.project_reports (previous_report_id)
  WHERE previous_report_id IS NOT NULL;

-- 6. Multilingual card summaries (originally 20260422234642_add_card_summary_multilingual_columns)
ALTER TABLE public.project_reports
  ADD COLUMN IF NOT EXISTS card_summary_fr text,
  ADD COLUMN IF NOT EXISTS card_summary_es text,
  ADD COLUMN IF NOT EXISTS card_summary_de text,
  ADD COLUMN IF NOT EXISTS card_summary_ja text,
  ADD COLUMN IF NOT EXISTS card_summary_zh text;
