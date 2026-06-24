-- BCE-2170: Correct GUSD tracked project display metadata.
--
-- The `gusd` tracked project is the Gate USD / Gate GUSD target used by
-- promoted analysis summary jobs. Gemini Dollar is a separate market identity
-- (`gemini-dollar`) and must not remain as the display name for this slug.

UPDATE public.tracked_projects
SET
  name = 'Gate USD',
  symbol = 'GUSD',
  aliases = ARRAY['gusd', 'gate usd', 'gate gusd', 'gateusd'],
  website_url = COALESCE(website_url, 'https://www.gate.com/gusd'),
  updated_at = now()
WHERE slug = 'gusd'
  AND (
    name IS DISTINCT FROM 'Gate USD'
    OR symbol IS DISTINCT FROM 'GUSD'
    OR aliases IS DISTINCT FROM ARRAY['gusd', 'gate usd', 'gate gusd', 'gateusd']
    OR website_url IS NULL
  );
