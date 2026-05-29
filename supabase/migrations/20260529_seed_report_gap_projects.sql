-- Seed Top 200 projects whose Drive Slide PDFs are present but cannot be
-- published until the slide watcher can resolve a canonical tracked_project.
-- These rows keep CMC snapshot slugs aligned with report-bearing project rows.

WITH project_seed(name, slug, symbol, category, coingecko_id, aliases) AS (
  VALUES
    (
      '1inch',
      '1inch',
      '1INCH',
      'DeFi',
      '1inch',
      ARRAY['1inch network', '1inch_network', '1inch-network']::text[]
    ),
    (
      'Fluid',
      'instadapp',
      'FLUID',
      'DeFi',
      'instadapp',
      ARRAY['fluid', 'fluid protocol', 'fluid_protocol', 'instadapp fluid']::text[]
    ),
    (
      'Vision',
      'vision',
      'VSN',
      'Infrastructure',
      'vision-3',
      ARRAY['vsn', 'vision token', 'vision-token']::text[]
    ),
    (
      'Newton',
      'newton',
      'N',
      'Infrastructure',
      NULL,
      ARRAY['newton protocol', 'newton_protocol', 'newt']::text[]
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
