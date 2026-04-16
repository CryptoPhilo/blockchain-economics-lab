/**
 * CoinGecko free API utility for fetching price and market data.
 * Used by the score/ranking page for real-time market data.
 */

export interface CoinGeckoPrice {
  usd: number
  usd_24h_change: number
  usd_market_cap: number
}

export type CoinGeckoPriceMap = Record<string, CoinGeckoPrice>

/**
 * Fetch prices, 24h change, and market cap for a list of CoinGecko IDs.
 * Returns a map of coingecko_id -> price data.
 * Gracefully returns an empty map on failure.
 */
export async function fetchCoinGeckoPrices(ids: string[]): Promise<CoinGeckoPriceMap> {
  if (ids.length === 0) return {}

  try {
    const url = `https://api.coingecko.com/api/v3/simple/price?ids=${ids.join(',')}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true`
    const res = await fetch(url, { next: { revalidate: 300 } }) // 5-minute ISR cache

    if (!res.ok) return {}

    const data = await res.json()
    const result: CoinGeckoPriceMap = {}

    for (const id of ids) {
      if (data[id]) {
        result[id] = {
          usd: data[id].usd ?? 0,
          usd_24h_change: data[id].usd_24h_change ?? 0,
          usd_market_cap: data[id].usd_market_cap ?? 0,
        }
      }
    }

    return result
  } catch {
    return {}
  }
}
