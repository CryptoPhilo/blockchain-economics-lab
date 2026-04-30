-- Migration: add_aliases_to_tracked_projects
-- Date: 2026-04-27
-- Description: Adds an `aliases` text[] column to tracked_projects so the
--              ingest pipeline can resolve Korean draft filenames whose
--              leading project name is not in the in-code KO_NAME_TO_SLUG
--              map. The pipeline performs an array overlap query against
--              `aliases` between the direct slug match and the symbol/name
--              fallbacks. Authoring new aliases is a data change instead of
--              a code change.
-- Related: BCE-1050, BCE-1046

ALTER TABLE tracked_projects
  ADD COLUMN IF NOT EXISTS aliases text[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS tracked_projects_aliases_gin_idx
  ON tracked_projects USING gin (aliases);

COMMENT ON COLUMN tracked_projects.aliases IS
  'Alternative slug fragments (Korean / locale-specific) used by the ingest pipeline to map draft filenames to the canonical project. Matched via PostgREST overlaps() against tokens derived from the raw filename slug.';

-- Seed: Korean aliases for projects already in tracked_projects.
-- UPDATE-by-slug is a no-op when the slug is absent, so this migration is
-- safe on databases with partial seed data. Aliases mirror the in-code
-- KO_NAME_TO_SLUG map plus the BCE-1046 backlog additions.
UPDATE tracked_projects SET aliases = ARRAY['비트코인']                                       WHERE slug = 'bitcoin';
UPDATE tracked_projects SET aliases = ARRAY['이더리움']                                       WHERE slug = 'ethereum';
UPDATE tracked_projects SET aliases = ARRAY['솔라나']                                         WHERE slug = 'solana';
UPDATE tracked_projects SET aliases = ARRAY['카르다노']                                       WHERE slug = 'cardano';
UPDATE tracked_projects SET aliases = ARRAY['리플']                                           WHERE slug = 'ripple';
UPDATE tracked_projects SET aliases = ARRAY['폴카닷']                                         WHERE slug = 'polkadot';
UPDATE tracked_projects SET aliases = ARRAY['체인링크']                                       WHERE slug = 'chainlink';
UPDATE tracked_projects SET aliases = ARRAY['아발란체']                                       WHERE slug = 'avalanche-2';
UPDATE tracked_projects SET aliases = ARRAY['니어']                                           WHERE slug = 'near';
UPDATE tracked_projects SET aliases = ARRAY['아비트럼']                                       WHERE slug = 'arbitrum';
UPDATE tracked_projects SET aliases = ARRAY['유니스왑']                                       WHERE slug = 'uniswap';
UPDATE tracked_projects SET aliases = ARRAY['아베']                                           WHERE slug = 'aave';
UPDATE tracked_projects SET aliases = ARRAY['트론']                                           WHERE slug = 'tron';
UPDATE tracked_projects SET aliases = ARRAY['도지코인']                                       WHERE slug = 'dogecoin';
UPDATE tracked_projects SET aliases = ARRAY['바이낸스코인']                                   WHERE slug = 'binancecoin';
UPDATE tracked_projects SET aliases = ARRAY['인터넷컴퓨터']                                   WHERE slug = 'internet-computer';
UPDATE tracked_projects SET aliases = ARRAY['폴리곤']                                         WHERE slug = 'matic-network';
UPDATE tracked_projects SET aliases = ARRAY['폴리곤']                                         WHERE slug = 'polygon-pos';
UPDATE tracked_projects SET aliases = ARRAY['비트코인-캐시', '비트코인캐시']                  WHERE slug = 'bitcoin-cash';
UPDATE tracked_projects SET aliases = ARRAY['스텔라']                                         WHERE slug = 'stellar';
UPDATE tracked_projects SET aliases = ARRAY['앱토스']                                         WHERE slug = 'aptos';
UPDATE tracked_projects SET aliases = ARRAY['리도-파이낸스', '리도파이낸스']                  WHERE slug = 'lido-dao';
UPDATE tracked_projects SET aliases = ARRAY['알고랜드']                                       WHERE slug = 'algorand';
UPDATE tracked_projects SET aliases = ARRAY['플레어', '플레어-네트워크', '플레어네트워크']    WHERE slug = 'flare-networks';
UPDATE tracked_projects SET aliases = ARRAY['온도-파이낸스', '온도파이낸스']                  WHERE slug = 'ondo-finance';
UPDATE tracked_projects SET aliases = ARRAY['테더']                                           WHERE slug = 'tether';
UPDATE tracked_projects SET aliases = ARRAY['헤데라']                                         WHERE slug = 'hedera-hashgraph';
UPDATE tracked_projects SET aliases = ARRAY['모네로']                                         WHERE slug = 'monero';
UPDATE tracked_projects SET aliases = ARRAY['하이퍼리퀴드']                                   WHERE slug = 'hyperliquid';
UPDATE tracked_projects SET aliases = ARRAY['스토리-프로토콜', '스토리프로토콜']              WHERE slug = 'story-protocol';
UPDATE tracked_projects SET aliases = ARRAY['월렛커넥트', '월릿커넥트']                       WHERE slug = 'walletconnect';
UPDATE tracked_projects SET aliases = ARRAY['월렛커넥트', '월릿커넥트']                       WHERE slug = 'wallet-connect';
UPDATE tracked_projects SET aliases = ARRAY['페이팔', '페이팔-usd', 'pyusd']                  WHERE slug = 'paypal-usd';
UPDATE tracked_projects SET aliases = ARRAY['라이트코인']                                     WHERE slug = 'litecoin';
UPDATE tracked_projects SET aliases = ARRAY['메이커다오', '스카이-프로토콜', '스카이프로토콜'] WHERE slug = 'maker';
UPDATE tracked_projects SET aliases = ARRAY['칸톤-네트워크', '칸톤네트워크', '칸톤']          WHERE slug = 'canton-network';
UPDATE tracked_projects SET aliases = ARRAY['월드-리버티-파이낸셜']                           WHERE slug = 'world-liberty-financial';
UPDATE tracked_projects SET aliases = ARRAY['리버-프로토콜', '리버프로토콜']                  WHERE slug = 'river-protocol';
UPDATE tracked_projects SET aliases = ARRAY['크로스']                                         WHERE slug = 'cross-crypto';
UPDATE tracked_projects SET aliases = ARRAY['맨틀-네트워크', '맨틀네트워크', '맨틀']          WHERE slug = 'mantle';
UPDATE tracked_projects SET aliases = ARRAY['테더-골드', '테더골드']                          WHERE slug = 'tether-gold';
UPDATE tracked_projects SET aliases = ARRAY['크로노스']                                       WHERE slug = 'cronos';
UPDATE tracked_projects SET aliases = ARRAY['파이-네트워크', '파이네트워크']                  WHERE slug = 'pi-network';
UPDATE tracked_projects SET aliases = ARRAY['게이트체인']                                     WHERE slug = 'gatechain';
UPDATE tracked_projects SET aliases = ARRAY['코스모스']                                       WHERE slug = 'cosmos';
UPDATE tracked_projects SET aliases = ARRAY['카스파']                                         WHERE slug = 'kaspa';
UPDATE tracked_projects SET aliases = ARRAY['렌더']                                           WHERE slug = 'render-token';
UPDATE tracked_projects SET aliases = ARRAY['파일코인']                                       WHERE slug = 'filecoin';
UPDATE tracked_projects SET aliases = ARRAY['이더리움클래식', '이더리움-클래식']              WHERE slug = 'ethereum-classic';
UPDATE tracked_projects SET aliases = ARRAY['비트겟']                                         WHERE slug = 'bitget-token';
UPDATE tracked_projects SET aliases = ARRAY['페페']                                           WHERE slug = 'pepe';
UPDATE tracked_projects SET aliases = ARRAY['팬케이크스왑']                                   WHERE slug = 'pancakeswap';
UPDATE tracked_projects SET aliases = ARRAY['오피셜-트럼프', '트럼프']                        WHERE slug = 'official-trump';
