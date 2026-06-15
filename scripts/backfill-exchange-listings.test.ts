import {
  buildEvidence,
  buildListingCandidates,
  CoinGeckoFetchError,
  fetchCoinGeckoExchange,
  getCoinGeckoRetryDelayMs,
  parseRetryAfterMs,
  processExchangeBackfillScope,
} from './backfill-exchange-listings'
import {
  CMC_TOP_30_EXCHANGE_SNAPSHOT_DATE,
  CMC_TOP_30_EXCHANGES,
  findCmcTop30ExchangeReference,
} from '../src/lib/exchange-top30'

function makeFetchResponse(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string) => headers[name.toLowerCase()] ?? null,
    },
    json: async () => body,
  } as Response
}

describe('buildListingCandidates', () => {
  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('keeps the CoinMarketCap Top 30 snapshot complete and slug-mapped', () => {
    expect(CMC_TOP_30_EXCHANGE_SNAPSHOT_DATE).toBe('2026-06-15')
    expect(CMC_TOP_30_EXCHANGES).toHaveLength(30)
    expect(new Set(CMC_TOP_30_EXCHANGES.map((exchange) => exchange.cmcRank)).size).toBe(30)
    expect(new Set(CMC_TOP_30_EXCHANGES.map((exchange) => exchange.slug)).size).toBe(30)
    expect(findCmcTop30ExchangeReference('coinbase')?.slug).toBe('coinbase')
    expect(findCmcTop30ExchangeReference('gdax')?.slug).toBe('coinbase')
    expect(findCmcTop30ExchangeReference('coinbase_exchange')?.slug).toBe('coinbase')
    expect(findCmcTop30ExchangeReference('coinbase-exchange')?.slug).toBe('coinbase')
    expect(findCmcTop30ExchangeReference('Coinbase Pro')?.slug).toBe('coinbase')
    expect(findCmcTop30ExchangeReference('bybit_spot')?.slug).toBe('bybit')
    expect(findCmcTop30ExchangeReference('Binance TR')?.coingeckoId).toBeNull()
  })

  it('matches CoinGecko ids, deduplicates pairs by project, and ignores ambiguous symbol matches', () => {
    const projects = [
      {
        id: 'bitcoin-id',
        slug: 'bitcoin',
        name: 'Bitcoin',
        symbol: 'BTC',
        coingecko_id: 'bitcoin',
        cmc_rank: 1,
        maturity_score: 80,
        status: 'active',
      },
      {
        id: 'ethereum-id',
        slug: 'ethereum',
        name: 'Ethereum',
        symbol: 'ETH',
        coingecko_id: null,
        cmc_rank: 2,
        maturity_score: null,
        status: 'monitoring_only',
      },
      {
        id: 'eth-duplicate-id',
        slug: 'eth-duplicate',
        name: 'ETH Duplicate',
        symbol: 'ETH',
        coingecko_id: null,
        cmc_rank: 2,
        maturity_score: null,
        status: 'active',
      },
      {
        id: 'archived-id',
        slug: 'archived',
        name: 'Archived',
        symbol: 'OLD',
        coingecko_id: 'old',
        cmc_rank: 5000,
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
          cmc_rank: 1,
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
          cmc_rank: 1200,
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

    const binance = findCmcTop30ExchangeReference('binance')

    expect(binance).not.toBeNull()
    expect(buildEvidence(binance!, candidates)).toEqual(expect.objectContaining({
      cmcRank: 1,
      coingeckoId: 'binance',
      listedProjectCount: 2,
      bceExchangeScore: 68.92,
      bceExchangeScoreFormulaVersion: 'bce-exchange-score-v1',
      bceExchangeScoreComponents: expect.objectContaining({
        coreBceQuality: 80,
        scoreCoverage: 70.71,
        longTailPenalty: 4.29,
      }),
      scoredProjectCount: 1,
    }))
  })

  it('parses CoinGecko Retry-After headers for bounded backoff', () => {
    const nowMs = Date.parse('2026-06-15T00:00:00.000Z')

    expect(parseRetryAfterMs('2', nowMs)).toBe(2000)
    expect(parseRetryAfterMs('120', nowMs)).toBe(60000)
    expect(parseRetryAfterMs('Mon, 15 Jun 2026 00:00:05 GMT', nowMs)).toBe(5000)
    expect(parseRetryAfterMs('not-a-date', nowMs)).toBeNull()
    expect(getCoinGeckoRetryDelayMs(1, '1', nowMs)).toBe(1500)
    expect(getCoinGeckoRetryDelayMs(3, null, nowMs)).toBe(6000)
  })

  it('retries recoverable CoinGecko 429 responses before reading tickers', async () => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined)
    const sleeps: number[] = []
    const fetchImpl = jest.fn()
      .mockResolvedValueOnce(makeFetchResponse(429, { error: 'rate limited' }, { 'retry-after': '1' }))
      .mockResolvedValueOnce(makeFetchResponse(200, {
        name: 'Binance',
        tickers: [{ coin_id: 'bitcoin', base: 'BTC', target: 'USDT' }],
      }))

    const result = await fetchCoinGeckoExchange('binance', 1, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      sleepMs: async (milliseconds) => {
        sleeps.push(milliseconds)
      },
      nowMs: () => Date.parse('2026-06-15T00:00:00.000Z'),
    })

    expect(fetchImpl).toHaveBeenCalledTimes(2)
    expect(sleeps).toEqual([1500])
    expect(result).toEqual({
      exchangeName: 'Binance',
      tickers: [{ coin_id: 'bitcoin', base: 'BTC', target: 'USDT' }],
    })
  })

  it('continues CMC Top 30 processing when one mapped venue exhausts retryable fetches', async () => {
    const failedVenue = findCmcTop30ExchangeReference('lbank')
    const continuedVenue = findCmcTop30ExchangeReference('binance')
    expect(failedVenue?.coingeckoId).toBe('lbank')
    expect(continuedVenue?.coingeckoId).toBe('binance')

    const fetchExchange = jest.fn()
      .mockRejectedValueOnce(new Error('CoinGecko lbank page 1 failed with HTTP 429'))
      .mockResolvedValueOnce({
        exchangeName: 'Binance',
        tickers: [{ coin_id: 'bitcoin', base: 'BTC', target: 'USDT', converted_volume: { usd: 10 } }],
      })

    const rows = await processExchangeBackfillScope(
      [failedVenue!, continuedVenue!],
      [{
        id: 'bitcoin-id',
        slug: 'bitcoin',
        name: 'Bitcoin',
        symbol: 'BTC',
        coingecko_id: 'bitcoin',
        cmc_rank: 1,
        maturity_score: 80,
        status: 'active',
      }],
      1,
      fetchExchange,
      true,
    )

    expect(fetchExchange).toHaveBeenCalledTimes(2)
    expect(rows[0]).toEqual(expect.objectContaining({
      reference: expect.objectContaining({ slug: 'lbank' }),
      candidates: [],
      skippedFetch: {
        exchangeSlug: 'lbank',
        coingeckoId: 'lbank',
        reason: 'CoinGecko lbank page 1 failed with HTTP 429',
      },
    }))
    expect(rows[1]).toEqual(expect.objectContaining({
      reference: expect.objectContaining({ slug: 'binance' }),
      candidates: [expect.objectContaining({ project: expect.objectContaining({ slug: 'bitcoin' }) })],
      skippedFetch: null,
    }))
  })

  it('keeps explicit exchange backfills fail-fast even when the venue is in the CMC Top 30 snapshot', async () => {
    const failedVenue = findCmcTop30ExchangeReference('lbank')
    expect(failedVenue?.coingeckoId).toBe('lbank')

    const fetchExchange = jest.fn()
      .mockRejectedValueOnce(new CoinGeckoFetchError('lbank', 1, 429, true))

    await expect(processExchangeBackfillScope(
      [failedVenue!],
      [],
      1,
      fetchExchange,
      false,
    )).rejects.toThrow('CoinGecko lbank page 1 failed with HTTP 429')
  })
})
