-- Preserve CoinMarketCap display metadata separately from stable site slugs.
-- This lets renamed projects such as Instadapp -> Fluid render with the
-- current CMC name/symbol without breaking existing report URLs.
ALTER TABLE market_data_daily
  ADD COLUMN IF NOT EXISTS cmc_name TEXT,
  ADD COLUMN IF NOT EXISTS cmc_symbol TEXT;
