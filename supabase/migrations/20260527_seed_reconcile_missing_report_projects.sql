-- Seed Top 200 projects whose Drive Slide PDFs existed, but whose canonical
-- tracked_projects rows were absent in production. Without these rows the
-- reconcile-only path can resolve neither project_id nor website-visible badges.

WITH project_seed(name, slug, symbol, category, coingecko_id, aliases) AS (
  VALUES
    (
      'Convex Finance',
      'convex-finance',
      'CVX',
      'DeFi',
      'convex-finance',
      ARRAY['convex', 'cvx']::text[]
    ),
    (
      'Golem Network Tokens',
      'golem-network-tokens',
      'GNT',
      'Infrastructure',
      'golem',
      ARRAY['golem', 'golem network', 'golem_network', 'gnt']::text[]
    ),
    (
      'MX Token',
      'mx-token',
      'MX',
      'Exchange Token',
      'mx-token',
      ARRAY['mexc', 'mx']::text[]
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
  'drive-report-reconcile-repair',
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
