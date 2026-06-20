-- BCE-1959: Exchange listing model for exchange pages and aggregate APIs.
--
-- Production writes must use the approved remote migration path. This migration
-- only defines the durable model; listing backfill remains a separate scoped run.

CREATE TABLE IF NOT EXISTS exchanges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE,
  name text NOT NULL,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive', 'delisted', 'archived')),
  website_url text,
  country text,
  source text,
  source_exchange_id text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS exchange_project_listings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exchange_id uuid NOT NULL REFERENCES exchanges(id) ON DELETE CASCADE,
  project_id uuid NOT NULL REFERENCES tracked_projects(id) ON DELETE CASCADE,
  listing_status text NOT NULL DEFAULT 'active'
    CHECK (listing_status IN ('active', 'inactive', 'delisted')),
  base_symbol text,
  quote_symbol text,
  pair text,
  source text,
  source_listing_id text,
  listed_at timestamptz,
  delisted_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (exchange_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_exchanges_status_slug
  ON exchanges (status, slug);

CREATE INDEX IF NOT EXISTS idx_exchange_project_listings_exchange_status
  ON exchange_project_listings (exchange_id, listing_status);

CREATE INDEX IF NOT EXISTS idx_exchange_project_listings_project_status
  ON exchange_project_listings (project_id, listing_status);

ALTER TABLE exchanges ENABLE ROW LEVEL SECURITY;
ALTER TABLE exchange_project_listings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can view active exchanges"
  ON exchanges
  FOR SELECT
  USING (status = 'active');

CREATE POLICY "Public can view active exchange listings"
  ON exchange_project_listings
  FOR SELECT
  USING (listing_status = 'active');

CREATE POLICY "Service role manages exchanges"
  ON exchanges
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role manages exchange listings"
  ON exchange_project_listings
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

COMMENT ON TABLE exchanges IS
  'Canonical exchange dimension for BCE exchange pages.';

COMMENT ON TABLE exchange_project_listings IS
  'One active/delisted relationship per exchange/project; active rows drive exchange aggregate counts and detail lists.';
