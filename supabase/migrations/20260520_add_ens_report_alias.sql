-- Ensure Drive slide filenames such as ENS_ECON_ko.pdf and ENS_MAT_ko.pdf
-- resolve to the canonical Ethereum Name Service tracked project.

UPDATE public.tracked_projects AS tp
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(
        COALESCE(tp.aliases, '{}'::text[])
        || ARRAY['ens']::text[]
      ) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE tp.slug = 'ethereum-name-service';
