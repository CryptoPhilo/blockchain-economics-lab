-- Migration: add_cmc_id_to_tracked_projects
-- Date: 2026-04-18
-- Description: Adds CoinMarketCap ID column to tracked_projects table
--              to support fallback data source for tokens not on CoinGecko.
-- Related: BCE-323

-- Add cmc_id column to tracked_projects
ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS cmc_id TEXT;

-- Create index for efficient CMC ID lookups
CREATE INDEX IF NOT EXISTS idx_tracked_projects_cmc_id ON tracked_projects(cmc_id) WHERE cmc_id IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN tracked_projects.cmc_id IS 'CoinMarketCap cryptocurrency ID (e.g., "bitcoin", "ethereum") for price data fallback when CoinGecko ID is unavailable';
