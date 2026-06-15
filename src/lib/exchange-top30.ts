export type CmcTop30ExchangeReference = {
  cmcRank: number
  cmcName: string
  slug: string
  coingeckoId: string | null
  aliases: string[]
}

// CoinMarketCap spot exchange ranking snapshot checked on 2026-06-15.
// Source: https://coinmarketcap.com/ko/rankings/exchanges/
export const CMC_TOP_30_EXCHANGE_SNAPSHOT_DATE = '2026-06-15'
export const CMC_TOP_30_EXCHANGE_SOURCE_URL = 'https://coinmarketcap.com/ko/rankings/exchanges/'

export const CMC_TOP_30_EXCHANGES: CmcTop30ExchangeReference[] = [
  { cmcRank: 1, cmcName: 'Binance', slug: 'binance', coingeckoId: 'binance', aliases: ['Binance'] },
  { cmcRank: 2, cmcName: 'Coinbase Exchange', slug: 'coinbase', coingeckoId: 'gdax', aliases: ['Coinbase', 'Coinbase Pro'] },
  { cmcRank: 3, cmcName: 'Upbit', slug: 'upbit', coingeckoId: 'upbit', aliases: ['Upbit'] },
  { cmcRank: 4, cmcName: 'OKX', slug: 'okx', coingeckoId: 'okex', aliases: ['OKEx'] },
  { cmcRank: 5, cmcName: 'Bybit', slug: 'bybit', coingeckoId: 'bybit_spot', aliases: ['Bybit Spot'] },
  { cmcRank: 6, cmcName: 'Bitget', slug: 'bitget', coingeckoId: 'bitget', aliases: ['Bitget'] },
  { cmcRank: 7, cmcName: 'Gate', slug: 'gate', coingeckoId: 'gate', aliases: ['Gate.io'] },
  { cmcRank: 8, cmcName: 'KuCoin', slug: 'kucoin', coingeckoId: 'kucoin', aliases: ['KuCoin'] },
  { cmcRank: 9, cmcName: 'MEXC', slug: 'mexc', coingeckoId: 'mxc', aliases: ['MEXC Global'] },
  { cmcRank: 10, cmcName: 'HTX', slug: 'htx', coingeckoId: 'huobi', aliases: ['Huobi'] },
  { cmcRank: 11, cmcName: 'Crypto.com Exchange', slug: 'crypto-com-exchange', coingeckoId: 'crypto_com', aliases: ['Crypto.com'] },
  { cmcRank: 12, cmcName: 'Bitfinex', slug: 'bitfinex', coingeckoId: 'bitfinex', aliases: ['Bitfinex'] },
  { cmcRank: 13, cmcName: 'BingX', slug: 'bingx', coingeckoId: 'bingx', aliases: ['BingX'] },
  { cmcRank: 14, cmcName: 'Kraken', slug: 'kraken', coingeckoId: 'kraken', aliases: ['Kraken'] },
  { cmcRank: 15, cmcName: 'Binance TR', slug: 'binance-tr', coingeckoId: null, aliases: ['Binance Turkey', 'Binance TR'] },
  { cmcRank: 16, cmcName: 'BitMart', slug: 'bitmart', coingeckoId: 'bitmart', aliases: ['BitMart'] },
  { cmcRank: 17, cmcName: 'LBank', slug: 'lbank', coingeckoId: 'lbank', aliases: ['LBank'] },
  { cmcRank: 18, cmcName: 'Bitstamp by Robinhood', slug: 'bitstamp', coingeckoId: 'bitstamp', aliases: ['Bitstamp'] },
  { cmcRank: 19, cmcName: 'Bithumb', slug: 'bithumb', coingeckoId: 'bithumb', aliases: ['Bithumb'] },
  { cmcRank: 20, cmcName: 'XT.COM', slug: 'xt', coingeckoId: 'xt', aliases: ['XT'] },
  { cmcRank: 21, cmcName: 'Tokocrypto', slug: 'tokocrypto', coingeckoId: 'toko_crypto', aliases: ['TokoCrypto'] },
  { cmcRank: 22, cmcName: 'bitFlyer', slug: 'bitflyer', coingeckoId: 'bitflyer', aliases: ['Bitflyer'] },
  { cmcRank: 23, cmcName: 'Binance.US', slug: 'binance-us', coingeckoId: 'binance_us', aliases: ['Binance US'] },
  { cmcRank: 24, cmcName: 'Gemini', slug: 'gemini', coingeckoId: 'gemini', aliases: ['Gemini'] },
  { cmcRank: 25, cmcName: 'Pionex', slug: 'pionex', coingeckoId: 'pionex', aliases: ['Pionex'] },
  { cmcRank: 26, cmcName: 'Toobit', slug: 'toobit', coingeckoId: 'toobit', aliases: ['Toobit'] },
  { cmcRank: 27, cmcName: 'Ourbit', slug: 'ourbit', coingeckoId: 'ourbit', aliases: ['Ourbit'] },
  { cmcRank: 28, cmcName: 'KCEX', slug: 'kcex', coingeckoId: 'kcex', aliases: ['KCEX'] },
  { cmcRank: 29, cmcName: 'CoinW', slug: 'coinw', coingeckoId: 'coinw', aliases: ['CoinW'] },
  { cmcRank: 30, cmcName: 'Deepcoin', slug: 'deepcoin', coingeckoId: 'deepcoin', aliases: ['Deepcoin'] },
]

export function findCmcTop30ExchangeReference(value: string): CmcTop30ExchangeReference | null {
  const normalized = value.trim().toLowerCase()
  return CMC_TOP_30_EXCHANGES.find((exchange) => (
    exchange.slug.toLowerCase() === normalized
    || exchange.coingeckoId?.toLowerCase() === normalized
    || exchange.cmcName.toLowerCase() === normalized
    || exchange.aliases.some((alias) => alias.toLowerCase() === normalized)
  )) ?? null
}
