-- BCE scoreboard identity fix:
-- Keep Circle EURC (CMC slug: euro-coin) separate from Societe Generale
-- EUR CoinVertible / EURCV (CMC slug: eur-coinvertible).

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[])) AS alias
      WHERE alias IS NOT NULL
        AND btrim(alias) <> ''
        AND lower(btrim(alias)) NOT IN (
          'eur-coinvertible',
          'euro-coinvertible',
          'eur coinvertible',
          'eurcv'
        )
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'eurc';

INSERT INTO tracked_projects (
  name,
  slug,
  symbol,
  category,
  status,
  discovery_source,
  cmc_id,
  aliases,
  updated_at
) VALUES (
  'EUR CoinVertible',
  'eur-coinvertible',
  'EURCV',
  'Stablecoins',
  'monitoring_only',
  'coinmarketcap',
  'eur-coinvertible',
  ARRAY['EUR CoinVertible', 'EURCV', 'eur-coinvertible', 'euro-coinvertible']::text[],
  now()
)
ON CONFLICT (slug) DO UPDATE
SET
  name = EXCLUDED.name,
  symbol = EXCLUDED.symbol,
  category = COALESCE(tracked_projects.category, EXCLUDED.category),
  status = CASE
    WHEN tracked_projects.status IN ('active', 'monitoring_only') THEN tracked_projects.status
    ELSE EXCLUDED.status
  END,
  discovery_source = COALESCE(tracked_projects.discovery_source, EXCLUDED.discovery_source),
  cmc_id = EXCLUDED.cmc_id,
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(tracked_projects.aliases, '{}'::text[]) || EXCLUDED.aliases) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now();
