/**
 * CoinMarketCap API utility for fetching price and market data.
 * Used as a fallback data source for tokens not available on CoinGecko.
 *
 * API Documentation: https://coinmarketcap.com/api/documentation/v1/
 */

export interface CMCPrice {
  usd: number
  usd_24h_change: number
  usd_market_cap: number
}

export type CMCPriceMap = Record<string, CMCPrice>

interface CMCQuoteUSD {
  price: number
  percent_change_24h: number
  market_cap: number
}

interface CMCCoinData {
  slug: string
  quote?: {
    USD: CMCQuoteUSD
  }
}

interface CMCMapItem {
  id: number
  name: string
  symbol: string
  slug: string
  rank: number | null
}

/**
 * Fetch prices, 24h change, and market cap for a list of CoinMarketCap slugs.
 * Returns a map of cmc_id (slug) -> price data.
 * Gracefully returns an empty map on failure.
 *
 * @param ids - Array of CoinMarketCap cryptocurrency slugs (e.g., ["bitcoin", "ethereum"])
 * @returns Map of slug to price data
 */
export async function fetchCMCPrices(ids: string[]): Promise<CMCPriceMap> {
  if (ids.length === 0) return {}

  const apiKey = process.env.COINMARKETCAP_API_KEY
  if (!apiKey) {
    console.warn('COINMARKETCAP_API_KEY not configured, skipping CMC price fetch')
    return {}
  }

  try {
    // CMC API uses slugs separated by commas
    const url = `https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?slug=${ids.join(',')}&convert=USD`

    const res = await fetch(url, {
      headers: {
        'X-CMC_PRO_API_KEY': apiKey,
        'Accept': 'application/json',
      },
      next: { revalidate: 300 }, // 5-minute ISR cache (same as CoinGecko)
    })

    if (!res.ok) {
      console.error(`CMC API error: ${res.status} ${res.statusText}`)
      return {}
    }

    const data = await res.json()
    const result: CMCPriceMap = {}

    // CMC response structure: { data: { "1": {...}, "1027": {...} }, status: {...} }
    // We need to map by slug, not by ID
    if (data.data) {
      for (const [, coinData] of Object.entries(data.data as Record<string, CMCCoinData>)) {
        const slug = coinData.slug
        const quote = coinData.quote?.USD

        if (slug && quote) {
          result[slug] = {
            usd: quote.price ?? 0,
            usd_24h_change: quote.percent_change_24h ?? 0,
            usd_market_cap: quote.market_cap ?? 0,
          }
        }
      }
    }

    return result
  } catch (error) {
    console.error('Error fetching CMC prices:', error)
    return {}
  }
}

/**
 * Search CoinMarketCap for a cryptocurrency by name or symbol.
 * Useful for discovering the correct CMC slug for a token.
 *
 * @param query - Token name or symbol to search for
 * @returns Array of matching cryptocurrencies with their slugs
 */
export async function searchCMC(query: string): Promise<Array<{
  id: number
  name: string
  symbol: string
  slug: string
  rank: number | null
}>> {
  const apiKey = process.env.COINMARKETCAP_API_KEY
  if (!apiKey) {
    console.warn('COINMARKETCAP_API_KEY not configured')
    return []
  }

  try {
    const url = `https://pro-api.coinmarketcap.com/v1/cryptocurrency/map?symbol=${encodeURIComponent(query)}`

    const res = await fetch(url, {
      headers: {
        'X-CMC_PRO_API_KEY': apiKey,
        'Accept': 'application/json',
      },
    })

    if (!res.ok) {
      console.error(`CMC search error: ${res.status} ${res.statusText}`)
      return []
    }

    const data = await res.json()

    if (data.data && Array.isArray(data.data)) {
      return data.data.map((item: CMCMapItem) => ({
        id: item.id,
        name: item.name,
        symbol: item.symbol,
        slug: item.slug,
        rank: item.rank ?? null,
      }))
    }

    return []
  } catch (error) {
    console.error('Error searching CMC:', error)
    return []
  }
}
