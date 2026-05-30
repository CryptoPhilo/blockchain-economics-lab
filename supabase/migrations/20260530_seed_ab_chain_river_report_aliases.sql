-- Keep Top 200 CMC rows and Drive report filenames aligned with canonical
-- report-bearing projects for rows whose CMC identity differs from the
-- report project naming convention.

WITH project_seed(name, slug, symbol, category, aliases) AS (
  VALUES
    (
      'AB Chain',
      'ab-chain',
      'AB',
      'Infrastructure',
      ARRAY['ab', 'ab chain', 'ab_chain', 'ab-chain']::text[]
    ),
    (
      'River',
      'river',
      'RIVER',
      'Infrastructure',
      ARRAY['river', 'river protocol', 'river_protocol', 'river-protocol']::text[]
    )
)
INSERT INTO tracked_projects (
  name,
  slug,
  symbol,
  category,
  status,
  discovery_source,
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
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(tracked_projects.aliases, '{}'::text[]) || EXCLUDED.aliases) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now();
