import {
  buildExchangeAggregates,
  buildExchangeProjectRows,
  type ExchangeProjectRecord,
  type ExchangeListingRecord,
} from './exchanges'

const binance = {
  id: 'exchange-binance',
  slug: 'binance',
  name: 'Binance',
  status: 'active',
  website_url: 'https://www.binance.com',
  country: null,
}

const coinbase = {
  id: 'exchange-coinbase',
  slug: 'coinbase',
  name: 'Coinbase',
  status: 'active',
  website_url: null,
  country: 'US',
}

const inactiveExchange = {
  id: 'exchange-archived',
  slug: 'archived',
  name: 'Archived',
  status: 'archived',
  website_url: null,
  country: null,
}

function project(overrides: Partial<ExchangeProjectRecord> & Pick<ExchangeProjectRecord, 'id' | 'slug' | 'name'>) {
  const { id, name, slug, ...rest } = overrides

  return {
    id,
    name,
    slug,
    symbol: slug.slice(0, 4).toUpperCase(),
    category: 'L1',
    market_cap_usd: 0,
    coingecko_id: null,
    cmc_id: null,
    aliases: null,
    maturity_score: null,
    last_econ_report_at: null,
    last_maturity_report_at: null,
    last_forensic_report_at: null,
    status: 'active',
    ...rest,
  }
}

const rows: ExchangeListingRecord[] = [
  {
    listing_status: 'active',
    exchange: binance,
    project: project({
      id: 'bitcoin',
      slug: 'bitcoin',
      name: 'Bitcoin',
      symbol: 'BTC',
      market_cap_usd: 100,
      maturity_score: 80,
      last_econ_report_at: '2026-06-01T00:00:00Z',
    }),
  },
  {
    listing_status: 'active',
    exchange: binance,
    project: project({
      id: 'ethereum',
      slug: 'ethereum',
      name: 'Ethereum',
      symbol: 'ETH',
      market_cap_usd: 90,
      maturity_score: null,
      status: 'monitoring_only',
    }),
  },
  {
    listing_status: 'active',
    exchange: binance,
    project: project({
      id: 'bitcoin',
      slug: 'bitcoin',
      name: 'Bitcoin duplicate pair',
      symbol: 'BTC',
      market_cap_usd: 100,
      maturity_score: 40,
    }),
  },
  {
    listing_status: 'delisted',
    exchange: binance,
    project: project({ id: 'solana', slug: 'solana', name: 'Solana', maturity_score: 70 }),
  },
  {
    listing_status: 'active',
    exchange: coinbase,
    project: project({ id: 'bitcoin', slug: 'bitcoin', name: 'Bitcoin', maturity_score: 80 }),
  },
  {
    listing_status: 'active',
    exchange: coinbase,
    project: project({ id: 'ethereum', slug: 'ethereum', name: 'Ethereum', maturity_score: 'not-a-score' }),
  },
  {
    listing_status: 'active',
    exchange: inactiveExchange,
    project: project({ id: 'aave', slug: 'aave', name: 'Aave', maturity_score: 50 }),
  },
  {
    listing_status: 'active',
    exchange: coinbase,
    project: project({ id: 'archived-project', slug: 'old', name: 'Old', status: 'archived' }),
  },
]

describe('exchange repository aggregation helpers', () => {
  it('deduplicates listings and excludes null scores from the BCE average', () => {
    const aggregates = buildExchangeAggregates(rows)

    expect(aggregates).toEqual([
      expect.objectContaining({
        slug: 'binance',
        listedProjectCount: 2,
        averageBceScore: 80,
        scoredProjectCount: 1,
      }),
      expect.objectContaining({
        slug: 'coinbase',
        listedProjectCount: 2,
        averageBceScore: 80,
        scoredProjectCount: 1,
      }),
    ])
  })

  it('returns Top500-compatible project rows for a slug or exact name match', () => {
    const detail = buildExchangeProjectRows(rows, 'Binance')

    expect(detail.exchange?.slug).toBe('binance')
    expect(detail.projects).toEqual([
      expect.objectContaining({
        rank: 1,
        slug: 'bitcoin',
        score: 80,
        reportTypes: ['econ'],
      }),
      expect.objectContaining({
        rank: 2,
        slug: 'ethereum',
        score: null,
        reportTypes: [],
      }),
    ])
  })
})
