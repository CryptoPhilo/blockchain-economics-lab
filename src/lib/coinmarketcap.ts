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
export type CMCPriceByIdMap = Record<number, CMCPrice>

export interface CMCListing {
  slug: string
  name: string
  symbol: string
  cmc_rank: number
  price_usd: number
  market_cap: number
  change_24h: number
  recorded_at: string
}

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

interface CMCListingData extends CMCCoinData {
  name: string
  symbol: string
  cmc_rank: number
}

interface CMCMapItem {
  id: number
  name: string
  symbol: string
  slug: string
  rank: number | null
}

function getCMCApiKey() {
  return process.env.COINMARKETCAP_API_KEY || process.env.CMC_API_KEY || ''
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

  const apiKey = getCMCApiKey()
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

export async function fetchCMCPricesByIds(ids: number[]): Promise<CMCPriceByIdMap> {
  if (ids.length === 0) return {}

  const apiKey = getCMCApiKey()
  if (!apiKey) return {}

  try {
    const url = `https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?id=${ids.join(',')}&convert=USD`
    const res = await fetch(url, {
      headers: {
        'X-CMC_PRO_API_KEY': apiKey,
        'Accept': 'application/json',
      },
      next: { revalidate: 300 },
    })

    if (!res.ok) return {}

    const data = await res.json()
    const result: CMCPriceByIdMap = {}

    if (data.data) {
      for (const [numericId, coinData] of Object.entries(data.data as Record<string, CMCCoinData & { id?: number }>)) {
        const quote = coinData.quote?.USD
        if (quote) {
          result[Number(numericId)] = {
            usd: quote.price ?? 0,
            usd_24h_change: quote.percent_change_24h ?? 0,
            usd_market_cap: quote.market_cap ?? 0,
          }
        }
      }
    }

    return result
  } catch {
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
  const apiKey = getCMCApiKey()
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

export async function fetchCMCTopListings(limit = 500): Promise<CMCListing[]> {
  const apiKey = getCMCApiKey()
  if (!apiKey) {
    console.warn('CMC API key not configured, skipping CMC listings fetch')
    return []
  }

  try {
    const boundedLimit = Math.max(1, Math.min(limit, 5000))
    const url = `https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest?start=1&limit=${boundedLimit}&sort=market_cap&convert=USD`
    const res = await fetch(url, {
      headers: {
        'X-CMC_PRO_API_KEY': apiKey,
        'Accept': 'application/json',
      },
      next: { revalidate: 300 },
    })

    if (!res.ok) {
      console.error(`CMC listings API error: ${res.status} ${res.statusText}`)
      return []
    }

    const payload = await res.json()
    const recordedAt = new Date().toISOString()
    const listings = Array.isArray(payload.data) ? payload.data as CMCListingData[] : []

    return listings
      .map((item) => {
        const quote = item.quote?.USD
        return {
          slug: item.slug,
          name: item.name,
          symbol: item.symbol,
          cmc_rank: item.cmc_rank,
          price_usd: quote?.price ?? 0,
          market_cap: quote?.market_cap ?? 0,
          change_24h: quote?.percent_change_24h ?? 0,
          recorded_at: recordedAt,
        }
      })
      .filter((item) => (
        item.slug
        && item.name
        && item.symbol
        && Number.isInteger(item.cmc_rank)
        && item.cmc_rank >= 1
        && item.cmc_rank <= boundedLimit
      ))
  } catch (error) {
    console.error('Error fetching CMC listings:', error)
    return []
  }
}
