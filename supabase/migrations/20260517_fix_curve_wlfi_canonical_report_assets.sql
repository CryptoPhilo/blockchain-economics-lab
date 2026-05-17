-- Keep CMC Top 200 rows joined to the canonical report-bearing projects for
-- Curve DAO and World Liberty Financial, and backfill Drive-confirmed localized
-- report assets that were split across duplicate project rows.

-- Curve DAO: CMC uses curve-dao-token, while the website canonical route is
-- curve-dao. Preserve the canonical project and archive the duplicate.
UPDATE tracked_projects
SET
  status = 'active',
  cmc_id = 6538,
  coingecko_id = COALESCE(coingecko_id, 'curve-dao-token'),
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['curve', 'crv', 'curve-dao-token']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'curve-dao';

UPDATE tracked_projects
SET status = 'archived', aliases = ARRAY[]::text[], updated_at = now()
WHERE slug = 'curve-dao-token'
  AND status IS DISTINCT FROM 'archived';

-- Curve Drive PDFs confirmed in Slide/ECON and Slide/MAT. The score page only
-- needs a locale-visible asset URL, but these rows also keep project pages and
-- future audits tied to the canonical project.
WITH curve_project AS (
  SELECT id FROM tracked_projects WHERE slug = 'curve-dao'
),
curve_assets(report_type, language, drive_file_id, title_en, title_ko, title_ja, title_zh, published_at) AS (
  VALUES
    ('econ'::report_type, 'en', '1-clKtWcg8bgVPbs79Z5afjStjntK0uiV', 'Curve ECON en', NULL, NULL, NULL, '2026-05-16T01:17:03Z'::timestamptz),
    ('econ'::report_type, 'ko', '11pI2exHDupktpJTUqmeG4z7SLZlKqbiJ', NULL, 'Curve ECON ko', NULL, NULL, '2026-05-16T02:02:01Z'::timestamptz),
    ('econ'::report_type, 'ja', '1K5B7bZbbuS2qC9CtqbNQqLzNDRfRd1QC', NULL, NULL, 'Curve ECON ja', NULL, '2026-05-16T03:07:06Z'::timestamptz),
    ('econ'::report_type, 'zh', '1qFVhLCI7pQSwq4w18Kze5o1Ld6eFbx04', NULL, NULL, NULL, 'Curve ECON zh', '2026-05-16T06:26:41Z'::timestamptz),
    ('maturity'::report_type, 'en', '1lGiwtopI4J8u5qt9HWsVf7x6MOB051Rm', 'Curve MAT en', NULL, NULL, NULL, '2026-05-16T01:43:00Z'::timestamptz),
    ('maturity'::report_type, 'ko', '1d8I5IynExhyv3_jijeTnPnpvg5C_wqxz', NULL, 'Curve MAT ko', NULL, NULL, '2026-05-16T05:03:42Z'::timestamptz),
    ('maturity'::report_type, 'ja', '1wso2hG9KQZwk6nOa-9fryrlso2PJRiuV', NULL, NULL, 'Curve MAT ja', NULL, '2026-05-16T08:03:04Z'::timestamptz),
    ('maturity'::report_type, 'zh', '1c3SDY5Th4p_3hdDu-xbJEWuk8SPgKvz0', NULL, NULL, NULL, 'Curve MAT zh', '2026-05-16T08:36:25Z'::timestamptz)
)
INSERT INTO project_reports (
  project_id,
  report_type,
  version,
  status,
  language,
  published_at,
  title_en,
  title_ko,
  title_ja,
  title_zh,
  gdrive_urls_by_lang,
  created_at,
  updated_at,
  is_latest
)
SELECT
  curve_project.id,
  curve_assets.report_type,
  1,
  'published'::report_status,
  curve_assets.language,
  curve_assets.published_at,
  curve_assets.title_en,
  curve_assets.title_ko,
  curve_assets.title_ja,
  curve_assets.title_zh,
  jsonb_build_object(
    curve_assets.language,
    jsonb_build_object(
      'url', 'https://drive.google.com/file/d/' || curve_assets.drive_file_id || '/view',
      'download_url', 'https://drive.google.com/uc?export=download&id=' || curve_assets.drive_file_id
    )
  ),
  curve_assets.published_at,
  now(),
  true
FROM curve_project
CROSS JOIN curve_assets
ON CONFLICT (project_id, report_type, version, language)
DO UPDATE SET
  status = 'published',
  published_at = COALESCE(project_reports.published_at, EXCLUDED.published_at),
  title_en = COALESCE(project_reports.title_en, EXCLUDED.title_en),
  title_ko = COALESCE(project_reports.title_ko, EXCLUDED.title_ko),
  title_ja = COALESCE(project_reports.title_ja, EXCLUDED.title_ja),
  title_zh = COALESCE(project_reports.title_zh, EXCLUDED.title_zh),
  gdrive_urls_by_lang = COALESCE(project_reports.gdrive_urls_by_lang, '{}'::jsonb) || EXCLUDED.gdrive_urls_by_lang,
  updated_at = now(),
  is_latest = true;

UPDATE tracked_projects
SET
  last_econ_report_at = GREATEST(
    COALESCE(last_econ_report_at, '-infinity'::timestamptz),
    '2026-05-16T06:26:41Z'::timestamptz
  ),
  last_maturity_report_at = GREATEST(
    COALESCE(last_maturity_report_at, '-infinity'::timestamptz),
    '2026-05-16T08:36:25Z'::timestamptz
  ),
  updated_at = now()
WHERE slug = 'curve-dao';

-- World Liberty Financial: keep the canonical website route and move reports
-- away from the archived CMC slug duplicate.
UPDATE tracked_projects
SET
  status = 'active',
  cmc_id = 33251,
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(
        COALESCE(aliases, '{}'::text[])
        || ARRAY['월드-리버티-파이낸셜', 'wlfi', 'world-liberty-financial-wlfi']
      ) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'world-liberty-financial';

WITH canonical AS (
  SELECT id FROM tracked_projects WHERE slug = 'world-liberty-financial'
),
duplicate AS (
  SELECT id FROM tracked_projects WHERE slug = 'world-liberty-financial-wlfi'
),
copied_reports AS (
  INSERT INTO project_reports (
    project_id,
    product_id,
    report_type,
    version,
    previous_report_id,
    is_latest,
    whitepaper_revision_ref,
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
    is_free,
    card_risk_score,
    card_keywords,
    card_summary_en,
    card_summary_ko,
    card_summary_fr,
    card_summary_es,
    card_summary_de,
    card_summary_ja,
    card_summary_zh,
    marketing_content_by_lang,
    card_data,
    file_url,
    file_urls_by_lang,
    gdrive_url,
    gdrive_download_url,
    gdrive_urls_by_lang,
    slide_html_urls_by_lang,
    page_count,
    task_id,
    title_en,
    title_ko,
    title_fr,
    title_es,
    title_de,
    title_ja,
    title_zh,
    translation_status,
    created_at,
    updated_at
  )
  SELECT
    canonical.id,
    source.product_id,
    source.report_type,
    source.version,
    NULL,
    source.is_latest,
    source.whitepaper_revision_ref,
    source.status,
    source.language,
    source.assigned_to,
    source.assigned_at,
    source.started_at,
    source.review_at,
    source.approved_at,
    source.published_at,
    source.trigger_reason,
    source.risk_level,
    source.is_free,
    source.card_risk_score,
    source.card_keywords,
    source.card_summary_en,
    source.card_summary_ko,
    source.card_summary_fr,
    source.card_summary_es,
    source.card_summary_de,
    source.card_summary_ja,
    source.card_summary_zh,
    source.marketing_content_by_lang,
    source.card_data,
    source.file_url,
    source.file_urls_by_lang,
    source.gdrive_url,
    source.gdrive_download_url,
    source.gdrive_urls_by_lang,
    source.slide_html_urls_by_lang,
    source.page_count,
    source.task_id,
    source.title_en,
    source.title_ko,
    source.title_fr,
    source.title_es,
    source.title_de,
    source.title_ja,
    source.title_zh,
    source.translation_status,
    source.created_at,
    now()
  FROM project_reports source
  CROSS JOIN canonical
  WHERE source.project_id = (SELECT id FROM duplicate)
    AND source.status IN ('published', 'coming_soon')
  ON CONFLICT (project_id, report_type, version, language)
  DO UPDATE SET
    status = EXCLUDED.status,
    is_latest = EXCLUDED.is_latest,
    published_at = COALESCE(project_reports.published_at, EXCLUDED.published_at),
    gdrive_urls_by_lang = COALESCE(project_reports.gdrive_urls_by_lang, '{}'::jsonb)
      || COALESCE(EXCLUDED.gdrive_urls_by_lang, '{}'::jsonb),
    file_urls_by_lang = COALESCE(project_reports.file_urls_by_lang, '{}'::jsonb)
      || COALESCE(EXCLUDED.file_urls_by_lang, '{}'::jsonb),
    slide_html_urls_by_lang = COALESCE(project_reports.slide_html_urls_by_lang, '{}'::jsonb)
      || COALESCE(EXCLUDED.slide_html_urls_by_lang, '{}'::jsonb),
    updated_at = now()
  RETURNING report_type
)
UPDATE tracked_projects
SET status = 'archived', aliases = ARRAY[]::text[], updated_at = now()
WHERE slug = 'world-liberty-financial-wlfi';

UPDATE tracked_projects
SET
  last_econ_report_at = COALESCE((
    SELECT max(published_at)
    FROM project_reports
    WHERE project_id = tracked_projects.id
      AND report_type = 'econ'
      AND status = 'published'
  ), last_econ_report_at),
  last_maturity_report_at = COALESCE((
    SELECT max(published_at)
    FROM project_reports
    WHERE project_id = tracked_projects.id
      AND report_type = 'maturity'
      AND status = 'published'
  ), last_maturity_report_at),
  updated_at = now()
WHERE slug = 'world-liberty-financial';
