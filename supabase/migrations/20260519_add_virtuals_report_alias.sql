-- Ensure operational short Drive slide filenames resolve to canonical tracked
-- projects without falling back to OCR/body matching.

WITH alias_patch(slug, new_aliases) AS (
  VALUES
    ('virtuals-protocol', ARRAY['virtuals', 'virtuals protocol']::text[]),
    ('zebec-network', ARRAY['zebec', 'zbcn']::text[])
)
UPDATE public.tracked_projects AS tp
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(
        COALESCE(tp.aliases, '{}'::text[])
        || alias_patch.new_aliases
      ) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
FROM alias_patch
WHERE tp.slug = alias_patch.slug;
