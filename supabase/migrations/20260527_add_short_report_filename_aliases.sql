-- Add operational short filename aliases used by Drive Slide report PDFs.
--
-- These aliases keep the database-level project vocabulary aligned with the
-- watcher alias registry so names like `story_ECON_ko.pdf` can resolve to the
-- canonical tracked project instead of becoming inactive Top 200 badges.

WITH alias_patch(slug, new_aliases) AS (
  VALUES
    ('story-protocol', ARRAY['story']::text[]),
    ('convex-finance', ARRAY['convex']::text[]),
    ('deepbook-protocol', ARRAY['deepbook']::text[]),
    ('golem-network-tokens', ARRAY['golem', 'golem network', 'golem_network']::text[]),
    ('mx-token', ARRAY['mexc']::text[])
)
UPDATE tracked_projects AS tp
SET aliases = (
  SELECT ARRAY(
    SELECT DISTINCT alias
    FROM unnest(COALESCE(tp.aliases, '{}'::text[]) || alias_patch.new_aliases) AS alias
    WHERE alias IS NOT NULL AND btrim(alias) <> ''
    ORDER BY alias
  )
),
updated_at = now()
FROM alias_patch
WHERE tp.slug = alias_patch.slug;
