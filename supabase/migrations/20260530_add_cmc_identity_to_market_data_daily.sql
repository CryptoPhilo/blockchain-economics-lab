-- Preserve the CoinMarketCap identity used by each canonical market snapshot row.
-- Scoreboard rows should display the CMC ticker/name for the ranked asset,
-- while still using tracked_projects only for report availability and scores.
ALTER TABLE market_data_daily
  ADD COLUMN IF NOT EXISTS cmc_symbol TEXT,
  ADD COLUMN IF NOT EXISTS cmc_name TEXT;

COMMENT ON COLUMN market_data_daily.cmc_symbol IS
  'CoinMarketCap symbol from the canonical market snapshot row.';
COMMENT ON COLUMN market_data_daily.cmc_name IS
  'CoinMarketCap name from the canonical market snapshot row.';
