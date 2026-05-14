-- BCE-1893 follow-up: keep Top 200 scoreboard slugs aligned with
-- canonical report-bearing projects.
--
-- The CMC snapshot can use newer market slugs while report production keeps
-- older canonical project slugs. These aliases and duplicate archives ensure
-- /score resolves to the project that owns the ECON report rows.

UPDATE tracked_projects
SET
  status = 'active',
  coingecko_id = 'polygon-ecosystem-token',
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(
        COALESCE(aliases, '{}'::text[])
        || ARRAY['폴리곤', 'polygon', 'matic', 'polygon-ecosystem-token', 'pol-ex-matic']
      ) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE id = 'd39823e2-39b0-481a-a477-7c9ba0027400'
  AND (
    status IS DISTINCT FROM 'active'
    OR coingecko_id IS DISTINCT FROM 'polygon-ecosystem-token'
    OR NOT ARRAY['폴리곤', 'polygon', 'matic', 'polygon-ecosystem-token', 'pol-ex-matic'] <@ COALESCE(aliases, '{}'::text[])
  );

UPDATE tracked_projects
SET status = 'archived', aliases = ARRAY[]::text[], updated_at = now()
WHERE id = '9cf32feb-17cf-46a8-85d7-fa8aa179cfcf'
  AND (status IS DISTINCT FROM 'archived' OR COALESCE(array_length(aliases, 1), 0) > 0);

UPDATE tracked_projects
SET
  status = 'active',
  cmc_id = 35766,
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['siren-bsc']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE id = 'c3f66120-41cd-4436-bb78-272467e42857'
  AND (
    status IS DISTINCT FROM 'active'
    OR cmc_id IS DISTINCT FROM 35766
    OR NOT ARRAY['siren-bsc'] <@ COALESCE(aliases, '{}'::text[])
  );

UPDATE tracked_projects
SET status = 'archived', aliases = ARRAY[]::text[], updated_at = now()
WHERE id = '5a261af9-b106-4e3f-806f-92173df2f709'
  AND (status IS DISTINCT FROM 'archived' OR COALESCE(array_length(aliases, 1), 0) > 0);

UPDATE tracked_projects
SET
  status = 'active',
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(
        COALESCE(aliases, '{}'::text[])
        || ARRAY['월드-리버티-파이낸셜', 'wlfi', 'world-liberty-financial-wlfi']
      ) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE id = '2ad729bb-86b8-4510-b77e-4a6635ff7a25'
  AND (
    status IS DISTINCT FROM 'active'
    OR NOT ARRAY['월드-리버티-파이낸셜', 'wlfi', 'world-liberty-financial-wlfi'] <@ COALESCE(aliases, '{}'::text[])
  );

UPDATE tracked_projects
SET status = 'archived', aliases = ARRAY[]::text[], updated_at = now()
WHERE id = '646fddfd-c26a-4cc3-8268-08e203980a9b'
  AND (status IS DISTINCT FROM 'archived' OR COALESCE(array_length(aliases, 1), 0) > 0);

UPDATE tracked_projects
SET
  status = 'active',
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(COALESCE(aliases, '{}'::text[]) || ARRAY['humanity']) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE id = '3c7ebda0-0d42-4c40-bd67-013b69839c07'
  AND (
    status IS DISTINCT FROM 'active'
    OR NOT ARRAY['humanity'] <@ COALESCE(aliases, '{}'::text[])
  );

UPDATE tracked_projects
SET status = 'archived', aliases = ARRAY[]::text[], updated_at = now()
WHERE id = '10b20804-6072-44cf-9927-4b36495f4191'
  AND (status IS DISTINCT FROM 'archived' OR COALESCE(array_length(aliases, 1), 0) > 0);

UPDATE tracked_projects
SET status = 'archived', aliases = ARRAY[]::text[], updated_at = now()
WHERE id = '2c08bc34-3d11-4df8-8420-9be3ae737f51'
  AND (status IS DISTINCT FROM 'archived' OR COALESCE(array_length(aliases, 1), 0) > 0);

UPDATE project_reports
SET
  status = 'published',
  published_at = COALESCE(published_at, NOW()),
  updated_at = NOW()
WHERE report_type = 'econ'
  AND status = 'in_review'
  AND project_id IN (
    '3c6e1565-e4e2-49a9-9769-de85918fb076',
    'e4b1d2d8-258c-4b0e-9fa0-bbfd81966213',
    'e6cb44ac-7eed-4fb1-b2a9-c413e3f27eae',
    'c0dc8afe-aa47-480b-8e60-1472ff32ed8f',
    '69eb801f-4421-4b97-84f3-8ead2d5a49f2',
    '6d0a741d-132d-47a0-9511-5edc5eeb6403',
    '2ad729bb-86b8-4510-b77e-4a6635ff7a25',
    'd39823e2-39b0-481a-a477-7c9ba0027400',
    'c3f66120-41cd-4436-bb78-272467e42857',
    '3c7ebda0-0d42-4c40-bd67-013b69839c07'
  );

UPDATE project_reports
SET
  status = 'published',
  published_at = COALESCE(published_at, NOW()),
  updated_at = NOW()
WHERE project_id = '2ad729bb-86b8-4510-b77e-4a6635ff7a25'
  AND report_type = 'econ'
  AND status = 'cancelled';
