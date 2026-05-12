-- Preserve CoinMarketCap canonical rank on each market snapshot row.
-- Existing rows stay nullable because historical snapshots did not store rank.
ALTER TABLE market_data_daily
  ADD COLUMN IF NOT EXISTS cmc_rank INTEGER,
  ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'coinmarketcap';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_data_daily_cmc_rank_positive'
  ) THEN
    ALTER TABLE market_data_daily
      ADD CONSTRAINT market_data_daily_cmc_rank_positive
      CHECK (cmc_rank IS NULL OR cmc_rank > 0);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_market_data_daily_recorded_at_cmc_rank
  ON market_data_daily (recorded_at DESC, cmc_rank ASC)
  WHERE source = 'coinmarketcap' AND cmc_rank IS NOT NULL;
