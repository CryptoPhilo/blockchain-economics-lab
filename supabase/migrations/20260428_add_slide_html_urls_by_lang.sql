-- BCE-1076: Add slide_html_urls_by_lang JSONB column to project_reports
-- Stores per-language HTML slide URLs (e.g. {"ko": "https://.../slug_econ_slide_ko.html", "en": "..."}).
-- Frontend SlideViewer reads this column to render language-specific slide decks.
-- Parent: BCE-1073

ALTER TABLE project_reports
  ADD COLUMN IF NOT EXISTS slide_html_urls_by_lang jsonb;

COMMENT ON COLUMN project_reports.slide_html_urls_by_lang IS
  'Per-language HTML slide URLs. Shape: {"<lang>": "<url>"}. Read by frontend SlideViewer (BCE-1073/BCE-1076).';
