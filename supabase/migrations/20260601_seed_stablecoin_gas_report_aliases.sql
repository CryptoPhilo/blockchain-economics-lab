-- Keep CMC Top 200 rows, Drive report filenames, and report-bearing projects
-- aligned for stablecoin and GAS rows whose public CMC identity differs from
-- the existing internal report/project naming.

WITH project_seed(name, slug, symbol, category, coingecko_id, aliases) AS (
  VALUES
    (
      'Gas',
      'gas',
      'GAS',
      'Layer 1',
      'gas',
      ARRAY['neo gas', 'neo-gas', 'gas token', 'neo gas token']::text[]
    )
)
INSERT INTO tracked_projects (
  name,
  slug,
  symbol,
  category,
  status,
  discovery_source,
  coingecko_id,
  aliases,
  created_at,
  updated_at
)
SELECT
  name,
  slug,
  symbol,
  category,
  'active'::project_status,
  'drive-report-gap-repair',
  coingecko_id,
  aliases,
  now(),
  now()
FROM project_seed
ON CONFLICT (slug) DO UPDATE
SET
  name = EXCLUDED.name,
  symbol = EXCLUDED.symbol,
  category = COALESCE(tracked_projects.category, EXCLUDED.category),
  status = CASE
    WHEN tracked_projects.status = 'archived' THEN 'active'::project_status
    ELSE tracked_projects.status
  END,
  discovery_source = COALESCE(tracked_projects.discovery_source, EXCLUDED.discovery_source),
  coingecko_id = COALESCE(tracked_projects.coingecko_id, EXCLUDED.coingecko_id),
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(tracked_projects.aliases, '{}'::text[]) || EXCLUDED.aliases) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now();

WITH alias_seed(slug, aliases) AS (
  VALUES
    (
      'usd1',
      ARRAY[
        'world liberty financial',
        'world-liberty-financial',
        'world liberty financial usd',
        'world-liberty-financial-usd',
        'world liberty usd',
        'wlfi stablecoin',
        'wlfi usd'
      ]::text[]
    ),
    (
      'dai',
      ARRAY[
        'multi-collateral-dai',
        'multi collateral dai',
        'makerdao dai'
      ]::text[]
    ),
    (
      'flare-networks',
      ARRAY[
        'flare',
        'flare network',
        'flare networks',
        'flr'
      ]::text[]
    )
)
UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(tracked_projects.aliases, '{}'::text[]) || alias_seed.aliases) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
FROM alias_seed
WHERE tracked_projects.slug = alias_seed.slug;

-- Historical Flare MAT rows were split between a legacy `flare` project and
-- the canonical Top 200 project `flare-networks`. Restore the canonical rows
-- from the legacy published assets so Korean/English score pages do not show a
-- false missing MAT badge.
WITH source_reports AS (
  SELECT
    source.*,
    target_project.id AS target_project_id
  FROM project_reports source
  JOIN tracked_projects source_project ON source_project.id = source.project_id
  JOIN tracked_projects target_project ON target_project.slug = 'flare-networks'
  WHERE source_project.slug = 'flare'
    AND source.report_type = 'maturity'
    AND source.status = 'published'
    AND source.language IN ('ko', 'en')
)
INSERT INTO project_reports (
  project_id,
  report_type,
  version,
  status,
  language,
  assigned_to,
  assigned_at,
  started_at,
  review_at,
  approved_at,
  published_at,
  trigger_reason,
  risk_level,
  file_url,
  page_count,
  task_id,
  title_en,
  title_ko,
  title_ja,
  title_zh,
  translation_status,
  file_urls_by_lang,
  gdrive_file_id,
  gdrive_url,
  gdrive_download_url,
  gdrive_folder_id,
  gdrive_urls_by_lang,
  gdrive_url_free,
  card_keywords,
  card_summary_en,
  card_summary_ko,
  card_summary_ja,
  card_summary_zh,
  card_thumbnail_url,
  card_risk_score,
  card_data,
  card_qa_status,
  previous_report_id,
  is_latest,
  whitepaper_revision_ref,
  slide_html_urls_by_lang,
  source_identity,
  source_file_id,
  source_modified_time,
  source_size,
  source_checksum,
  source_filename,
  created_at,
  updated_at
)
SELECT
  target_project_id,
  report_type,
  version,
  'published'::report_status,
  language,
  assigned_to,
  assigned_at,
  started_at,
  review_at,
  approved_at,
  COALESCE(published_at, updated_at, now()),
  trigger_reason,
  risk_level,
  file_url,
  page_count,
  task_id,
  title_en,
  title_ko,
  title_ja,
  title_zh,
  translation_status,
  COALESCE(file_urls_by_lang, '{}'::jsonb),
  gdrive_file_id,
  gdrive_url,
  gdrive_download_url,
  gdrive_folder_id,
  COALESCE(gdrive_urls_by_lang, '{}'::jsonb),
  gdrive_url_free,
  card_keywords,
  card_summary_en,
  card_summary_ko,
  card_summary_ja,
  card_summary_zh,
  card_thumbnail_url,
  card_risk_score,
  card_data,
  card_qa_status,
  previous_report_id,
  true,
  whitepaper_revision_ref,
  COALESCE(slide_html_urls_by_lang, '{}'::jsonb),
  concat_ws(
    '|',
    'canonical-flare-mat',
    target_project_id::text,
    report_type::text,
    language,
    gdrive_file_id,
    'version:' || version::text
  ),
  source_file_id,
  source_modified_time,
  source_size,
  source_checksum,
  source_filename,
  created_at,
  now()
FROM source_reports
ON CONFLICT (project_id, report_type, version, language) DO UPDATE
SET
  status = 'published'::report_status,
  published_at = COALESCE(project_reports.published_at, EXCLUDED.published_at),
  gdrive_file_id = COALESCE(project_reports.gdrive_file_id, EXCLUDED.gdrive_file_id),
  gdrive_url = COALESCE(project_reports.gdrive_url, EXCLUDED.gdrive_url),
  gdrive_download_url = COALESCE(project_reports.gdrive_download_url, EXCLUDED.gdrive_download_url),
  gdrive_folder_id = COALESCE(project_reports.gdrive_folder_id, EXCLUDED.gdrive_folder_id),
  gdrive_urls_by_lang = COALESCE(project_reports.gdrive_urls_by_lang, '{}'::jsonb)
    || COALESCE(EXCLUDED.gdrive_urls_by_lang, '{}'::jsonb),
  file_urls_by_lang = COALESCE(project_reports.file_urls_by_lang, '{}'::jsonb)
    || COALESCE(EXCLUDED.file_urls_by_lang, '{}'::jsonb),
  slide_html_urls_by_lang = COALESCE(project_reports.slide_html_urls_by_lang, '{}'::jsonb)
    || COALESCE(EXCLUDED.slide_html_urls_by_lang, '{}'::jsonb),
  source_file_id = COALESCE(project_reports.source_file_id, EXCLUDED.source_file_id),
  source_identity = COALESCE(project_reports.source_identity, EXCLUDED.source_identity),
  source_filename = COALESCE(project_reports.source_filename, EXCLUDED.source_filename),
  is_latest = true,
  updated_at = now();

UPDATE tracked_projects target_project
SET
  last_maturity_report_at = latest_report.latest_at,
  updated_at = now()
FROM (
  SELECT
    target_project.id AS project_id,
    max(COALESCE(report.published_at, report.updated_at, report.created_at)) AS latest_at
  FROM project_reports report
  JOIN tracked_projects target_project ON target_project.id = report.project_id
  WHERE target_project.slug = 'flare-networks'
    AND report.report_type = 'maturity'
    AND report.status = 'published'
    AND report.is_latest = true
  GROUP BY target_project.id
) latest_report
WHERE target_project.id = latest_report.project_id
  AND (
    target_project.last_maturity_report_at IS NULL
    OR target_project.last_maturity_report_at < latest_report.latest_at
  );
