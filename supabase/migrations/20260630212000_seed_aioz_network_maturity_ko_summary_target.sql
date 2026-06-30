-- Create the missing AIOZ Network target required by the Analysis Markdown
-- Summary Authority Gate. The gate promotes validated summary candidates into
-- existing project/report rows; it must not create those targets implicitly.

WITH project_seed(name, slug, symbol, category, coingecko_id, aliases) AS (
  VALUES
    (
      'AIOZ Network',
      'aioz-network',
      'AIOZ',
      'DePIN',
      'aioz-network',
      ARRAY[
        'aioz',
        'aioz network',
        'aioz-network',
        'aioz blockchain',
        'aioz depin'
      ]::text[]
    )
)
INSERT INTO public.tracked_projects (
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
  'analysis-md-summary-target-repair',
  coingecko_id,
  aliases,
  now(),
  now()
FROM project_seed
ON CONFLICT (slug) DO UPDATE
SET
  name = EXCLUDED.name,
  symbol = EXCLUDED.symbol,
  category = COALESCE(public.tracked_projects.category, EXCLUDED.category),
  status = CASE
    WHEN public.tracked_projects.status = 'archived'::project_status
      THEN 'active'::project_status
    ELSE public.tracked_projects.status
  END,
  discovery_source = COALESCE(
    public.tracked_projects.discovery_source,
    EXCLUDED.discovery_source
  ),
  coingecko_id = COALESCE(
    public.tracked_projects.coingecko_id,
    EXCLUDED.coingecko_id
  ),
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(
        COALESCE(public.tracked_projects.aliases, '{}'::text[])
        || EXCLUDED.aliases
      ) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now();

WITH target_project AS (
  SELECT id
  FROM public.tracked_projects
  WHERE slug = 'aioz-network'
  LIMIT 1
)
INSERT INTO public.project_reports (
  project_id,
  report_type,
  version,
  status,
  language,
  published_at,
  title_en,
  title_ko,
  translation_status,
  file_urls_by_lang,
  gdrive_urls_by_lang,
  slide_html_urls_by_lang,
  card_data,
  is_latest,
  source_identity,
  source_filename,
  created_at,
  updated_at
)
SELECT
  target_project.id,
  'maturity',
  1,
  'coming_soon'::report_status,
  'ko',
  NULL,
  'AIOZ Network Maturity Report',
  'AIOZ Network 성숙도 평가 보고서',
  jsonb_build_object('ko', 'coming_soon'),
  '{}'::jsonb,
  '{}'::jsonb,
  '{}'::jsonb,
  jsonb_build_object(
    'report_type', 'maturity',
    'slug', 'aioz-network',
    'summary_authority_target', jsonb_build_object(
      'issue', 'BCE-2330',
      'blocked_issue', 'BCE-2329',
      'job_id', 'd74bc166-b9ef-421d-8c9a-875939ed706c',
      'source_identity', 'drive:13Bj-oq6W6mACE1_86xYzS6W2RYeARsr6:0B8HYgThT3NByQlUxUEtsTzVPTjFJMEswNFdSNWliVDQvLzBzPQ',
      'drive_file_id', '13Bj-oq6W6mACE1_86xYzS6W2RYeARsr6',
      'revision_id', '0B8HYgThT3NByQlUxUEtsTzVPTjFJMEswNFdSNWliVDQvLzBzPQ',
      'created_for', 'Summary Authority Gate target backfill'
    )
  ),
  true,
  'summary-authority-target:aioz-network/maturity/ko/version:1',
  'AIOZ 크립토 이코노미 성숙도 평가 보고서_ AIOZ Network.md',
  now(),
  now()
FROM target_project
WHERE NOT EXISTS (
  SELECT 1
  FROM public.project_reports existing
  WHERE existing.project_id = target_project.id
    AND existing.report_type::text = 'maturity'
    AND existing.version = 1
    AND existing.language = 'ko'
)
ON CONFLICT (project_id, report_type, version, language) DO UPDATE
SET
  status = CASE
    WHEN public.project_reports.status = 'cancelled'::report_status
      THEN 'coming_soon'::report_status
    ELSE public.project_reports.status
  END,
  translation_status = CASE
    WHEN public.project_reports.status = 'cancelled'::report_status
      THEN COALESCE(public.project_reports.translation_status, '{}'::jsonb)
        || jsonb_build_object('ko', 'coming_soon')
    ELSE public.project_reports.translation_status
  END,
  card_data = COALESCE(public.project_reports.card_data, '{}'::jsonb)
    || jsonb_build_object(
      'summary_authority_target',
      jsonb_build_object(
        'issue', 'BCE-2330',
        'blocked_issue', 'BCE-2329',
        'job_id', 'd74bc166-b9ef-421d-8c9a-875939ed706c',
        'source_identity', 'drive:13Bj-oq6W6mACE1_86xYzS6W2RYeARsr6:0B8HYgThT3NByQlUxUEtsTzVPTjFJMEswNFdSNWliVDQvLzBzPQ',
        'drive_file_id', '13Bj-oq6W6mACE1_86xYzS6W2RYeARsr6',
        'revision_id', '0B8HYgThT3NByQlUxUEtsTzVPTjFJMEswNFdSNWliVDQvLzBzPQ',
        'created_for', 'Summary Authority Gate target backfill'
      )
    ),
  is_latest = CASE
    WHEN public.project_reports.status = 'cancelled'::report_status THEN true
    ELSE public.project_reports.is_latest
  END,
  source_identity = COALESCE(
    public.project_reports.source_identity,
    EXCLUDED.source_identity
  ),
  source_filename = COALESCE(
    public.project_reports.source_filename,
    EXCLUDED.source_filename
  ),
  updated_at = now();

UPDATE public.tracked_projects target_project
SET
  last_maturity_report_at = COALESCE(
    target_project.last_maturity_report_at,
    report_target.updated_at,
    now()
  ),
  updated_at = now()
FROM public.project_reports report_target
WHERE target_project.slug = 'aioz-network'
  AND report_target.project_id = target_project.id
  AND report_target.report_type::text = 'maturity'
  AND report_target.version = 1
  AND report_target.language = 'ko'
  AND report_target.status IN ('published', 'coming_soon', 'in_review');
