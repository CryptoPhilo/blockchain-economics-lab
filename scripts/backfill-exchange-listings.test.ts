import { buildEvidence, buildListingCandidates } from './backfill-exchange-listings'

describe('buildListingCandidates', () => {
  it('matches CoinGecko ids, deduplicates pairs by project, and ignores ambiguous symbol matches', () => {
    const projects = [
      {
        id: 'bitcoin-id',
        slug: 'bitcoin',
        name: 'Bitcoin',
        symbol: 'BTC',
        coingecko_id: 'bitcoin',
        maturity_score: 80,
        status: 'active',
      },
      {
        id: 'ethereum-id',
        slug: 'ethereum',
        name: 'Ethereum',
        symbol: 'ETH',
        coingecko_id: null,
        maturity_score: null,
        status: 'monitoring_only',
      },
      {
        id: 'eth-duplicate-id',
        slug: 'eth-duplicate',
        name: 'ETH Duplicate',
        symbol: 'ETH',
        coingecko_id: null,
        maturity_score: null,
        status: 'active',
      },
      {
        id: 'archived-id',
        slug: 'archived',
        name: 'Archived',
        symbol: 'OLD',
        coingecko_id: 'old',
        maturity_score: 10,
        status: 'archived',
      },
    ]

    const candidates = buildListingCandidates('binance', 'Binance', [
      {
        coin_id: 'bitcoin',
        base: 'BTC',
        target: 'USDT',
        converted_volume: { usd: 100 },
      },
      {
        coin_id: 'bitcoin',
        base: 'BTC',
        target: 'FDUSD',
        converted_volume: { usd: 200 },
      },
      {
        base: 'ETH',
        target: 'USDT',
        converted_volume: { usd: 300 },
      },
      {
        coin_id: 'old',
        base: 'OLD',
        target: 'USDT',
        converted_volume: { usd: 400 },
      },
    ], projects)

    expect(candidates).toHaveLength(1)
    expect(candidates[0]).toEqual(expect.objectContaining({
      exchangeSlug: 'binance',
      project: expect.objectContaining({ slug: 'bitcoin' }),
      pair: 'BTC/FDUSD',
      volumeUsd: 200,
      matchMethod: 'coingecko_id',
    }))
  })

  it('excludes null scores from aggregate evidence', () => {
    const candidates = [
      {
        exchangeSlug: 'binance',
        exchangeName: 'Binance',
        project: {
          id: 'bitcoin-id',
          slug: 'bitcoin',
          name: 'Bitcoin',
          symbol: 'BTC',
          coingecko_id: 'bitcoin',
          maturity_score: 80,
          status: 'active',
        },
        baseSymbol: 'BTC',
        quoteSymbol: 'USDT',
        pair: 'BTC/USDT',
        sourceListingId: 'binance:bitcoin:BTC/USDT',
        tradeUrl: null,
        trustScore: null,
        volumeUsd: 100,
        matchMethod: 'coingecko_id' as const,
      },
      {
        exchangeSlug: 'binance',
        exchangeName: 'Binance',
        project: {
          id: 'new-id',
          slug: 'new',
          name: 'New',
          symbol: 'NEW',
          coingecko_id: 'new',
          maturity_score: null,
          status: 'active',
        },
        baseSymbol: 'NEW',
        quoteSymbol: 'USDT',
        pair: 'NEW/USDT',
        sourceListingId: 'binance:new:NEW/USDT',
        tradeUrl: null,
        trustScore: null,
        volumeUsd: 50,
        matchMethod: 'coingecko_id' as const,
      },
    ]

    expect(buildEvidence('binance', 'Binance', candidates)).toEqual(expect.objectContaining({
      listedProjectCount: 2,
      averageBceScore: 80,
      scoredProjectCount: 1,
    }))
  })
})
