-- Fix report publication aliases that caused Drive-backed ECON/MAT reports to
-- miss the 200-rank scoreboard after filename-first matching was tightened.

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
VALUES (
  'Immutable X',
  'immutable-x',
  'IMX',
  'NFT',
  'active',
  'scoreboard-report-alias-repair',
  'immutable-x',
  ARRAY['immutable', 'imx']::text[],
  now(),
  now()
)
ON CONFLICT (slug) DO UPDATE
SET
  name = EXCLUDED.name,
  symbol = EXCLUDED.symbol,
  category = COALESCE(tracked_projects.category, EXCLUDED.category),
  status = CASE
    WHEN tracked_projects.status = 'archived' THEN 'active'::project_status
    ELSE tracked_projects.status
  END,
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
VALUES (
  'World Liberty Financial',
  'world-liberty-financial',
  'WLFI',
  'DeFi',
  'active',
  'scoreboard-report-alias-repair',
  'world-liberty-financial',
  ARRAY['wlfi']::text[],
  now(),
  now()
)
ON CONFLICT (slug) DO UPDATE
SET
  name = EXCLUDED.name,
  symbol = EXCLUDED.symbol,
  category = COALESCE(tracked_projects.category, EXCLUDED.category),
  status = CASE
    WHEN tracked_projects.status = 'archived' THEN 'active'::project_status
    ELSE tracked_projects.status
  END,
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

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['asi', 'fetch-ai', 'fetch ai', 'fet']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'artificial-superintelligence-alliance';

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['wlfi']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'world-liberty-financial';

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['pyth', 'pyth_network']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'pyth-network';

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['lido']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'lido-dao';

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['aerodrome']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'aerodrome-finance';

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['bttc']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'bittorrent';
