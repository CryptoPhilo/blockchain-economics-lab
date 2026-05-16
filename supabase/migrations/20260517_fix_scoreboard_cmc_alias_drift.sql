-- Keep the Top 200 scoreboard joined to report-bearing canonical projects when
-- CoinMarketCap uses market slugs that differ from BCELab report project slugs.

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['sei-network']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'sei'
  AND NOT ARRAY['sei-network'] <@ COALESCE(aliases, '{}'::text[]);

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['pancakeswap-token']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'pancakeswap'
  AND NOT ARRAY['pancakeswap-token'] <@ COALESCE(aliases, '{}'::text[]);

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['injective-protocol']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'injective'
  AND NOT ARRAY['injective-protocol'] <@ COALESCE(aliases, '{}'::text[]);

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['curve-dao-token']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'curve-dao'
  AND NOT ARRAY['curve-dao-token'] <@ COALESCE(aliases, '{}'::text[]);

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['blockstack']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'stacks'
  AND NOT ARRAY['blockstack'] <@ COALESCE(aliases, '{}'::text[]);

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['fetch-ai']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'artificial-superintelligence-alliance'
  AND NOT ARRAY['fetch-ai'] <@ COALESCE(aliases, '{}'::text[]);

UPDATE tracked_projects
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['euro-coin']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE slug = 'eurc'
  AND NOT ARRAY['euro-coin'] <@ COALESCE(aliases, '{}'::text[]);
