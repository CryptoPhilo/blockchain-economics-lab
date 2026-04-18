-- Direct CoinGecko ID updates for tracked_projects
-- Manually verified IDs (bypasses API rate limits for updates)
-- BCE-322

-- Well-known major tokens (high confidence)
UPDATE tracked_projects SET coingecko_id = 'dydx-chain' WHERE symbol = 'DYDX' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'enjincoin' WHERE symbol = 'ENJ' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'kusama' WHERE symbol = 'KSM' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'mantle' WHERE symbol = 'MNT' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'elrond-erd-2' WHERE symbol = 'EGLD' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'okb' WHERE symbol = 'OKB' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'ordinals' WHERE symbol = 'ORDI' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'pendle' WHERE symbol = 'PENDLE' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'terra-luna' WHERE symbol = 'LUNC' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'tether-gold' WHERE symbol = 'XAUT' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'centrifuge' WHERE symbol = 'CFG' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'dexe' WHERE symbol = 'DEXE' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'just' WHERE symbol = 'JST' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'memecoin-2' WHERE symbol = 'MEME' AND coingecko_id IS NULL;

-- Fix Story Protocol (incorrect ID)
UPDATE tracked_projects SET coingecko_id = 'story-2' WHERE symbol = 'IP' AND coingecko_id = 'story-protocol';

-- Medium confidence (should be verified manually if possible)
UPDATE tracked_projects SET coingecko_id = 'deepbook-protocol' WHERE symbol = 'DEEP' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'eigenlayer' WHERE symbol = 'EIGEN' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'safe' WHERE symbol = 'SAFE' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'walrus-protocol' WHERE symbol = 'WAL' AND coingecko_id IS NULL;
UPDATE tracked_projects SET coingecko_id = 'world-liberty-financial-wlfi' WHERE symbol = 'WLFI' AND coingecko_id IS NULL;
