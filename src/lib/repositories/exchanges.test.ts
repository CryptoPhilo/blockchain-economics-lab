import {
  applyProjectReportAvailabilityAliases,
  applyLatestCmcRanks,
  buildExchangeAggregates,
  buildExchangeProjectRows,
  calculateBceExchangeScore,
  getMissingProjectMarketDataKeys,
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

const legacyGdax = {
  id: 'exchange-gdax',
  slug: 'gdax',
  name: 'Coinbase Exchange',
  status: 'active',
  website_url: null,
  country: 'US',
}

const bybit = {
  id: 'exchange-bybit',
  slug: 'bybit',
  name: 'Bybit',
  status: 'active',
  website_url: null,
  country: null,
}

const okx = {
  id: 'exchange-okx',
  slug: 'okx',
  name: 'OKX',
  status: 'active',
  website_url: null,
  country: null,
}

const alpha = {
  id: 'exchange-alpha',
  slug: 'alpha',
  name: 'Alpha',
  status: 'active',
  website_url: null,
  country: null,
}

const beta = {
  id: 'exchange-beta',
  slug: 'beta',
  name: 'Beta',
  status: 'active',
  website_url: null,
  country: null,
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
    cmc_rank: null,
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
      cmc_rank: 1,
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
      cmc_rank: 2,
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
      cmc_rank: 1,
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
    project: project({ id: 'bitcoin', slug: 'bitcoin', name: 'Bitcoin', cmc_rank: 1, maturity_score: 80 }),
  },
  {
    listing_status: 'active',
    exchange: coinbase,
    project: project({ id: 'ethereum', slug: 'ethereum', name: 'Ethereum', cmc_rank: 1200, maturity_score: 'not-a-score' }),
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
  it('deduplicates listings and applies BCE Exchange Score v1 instead of a simple average', () => {
    const aggregates = buildExchangeAggregates({
      exchanges: [binance, coinbase, bybit],
      listings: rows,
    })

    expect(aggregates).toEqual([
      expect.objectContaining({
        slug: 'binance',
        listedProjectCount: 2,
        bceExchangeScore: 82.59,
        bceExchangeScoreFormulaVersion: 'bce-exchange-score-v1',
        scoredProjectCount: 1,
        bceExchangeScoreComponents: expect.objectContaining({
          coreBceQuality: 80,
          rankQuality: 95.93,
          scoreCoverage: 70.71,
          longTailPenalty: 0,
          listedProjectCount: 2,
          scoredProjectCount: 1,
          longTailRatio: 0,
        }),
      }),
      expect.objectContaining({
        slug: 'coinbase',
        listedProjectCount: 2,
        bceExchangeScore: 68.92,
        scoredProjectCount: 1,
        bceExchangeScoreComponents: expect.objectContaining({
          longTailPenalty: 4.29,
          longTailRatio: 0.5,
        }),
      }),
      expect.objectContaining({
        slug: 'bybit',
        listedProjectCount: 0,
        bceExchangeScore: null,
        scoredProjectCount: 0,
      }),
    ])
  })

  it('penalizes low-rank or missing-rank long-tail listings versus a simple scored average', () => {
    const result = calculateBceExchangeScore([
      project({ id: 'core', slug: 'core', name: 'Core', cmc_rank: 20, maturity_score: 90 }),
      project({ id: 'tail-1', slug: 'tail-1', name: 'Tail 1', cmc_rank: 2200, maturity_score: 90 }),
      project({ id: 'tail-2', slug: 'tail-2', name: 'Tail 2', cmc_rank: null, maturity_score: null }),
      project({ id: 'tail-3', slug: 'tail-3', name: 'Tail 3', cmc_rank: 6000, maturity_score: null }),
    ])

    expect(result.bceExchangeScore).toBeLessThan(90)
    expect(result.bceExchangeScoreComponents.longTailRatio).toBe(0.75)
    expect(result.bceExchangeScoreComponents.longTailPenalty).toBeGreaterThan(0)
  })

  it('keeps CMC Top 30 exchanges visible when no listing rows match', () => {
    const aggregates = buildExchangeAggregates({
      exchanges: [bybit],
      listings: [],
    })

    expect(aggregates).toEqual([
      expect.objectContaining({
        slug: 'bybit',
        name: 'Bybit',
        listedProjectCount: 0,
        bceExchangeScore: null,
      }),
    ])
  })

  it('suppresses legacy CMC alias exchange duplicates in aggregate lists', () => {
    const aggregates = buildExchangeAggregates({
      exchanges: [legacyGdax, coinbase],
      listings: [
        {
          listing_status: 'active',
          exchange: legacyGdax,
          project: project({ id: 'bitcoin', slug: 'bitcoin', name: 'Bitcoin', cmc_rank: 1, maturity_score: 80 }),
        },
        {
          listing_status: 'active',
          exchange: coinbase,
          project: project({ id: 'bitcoin', slug: 'bitcoin', name: 'Bitcoin', cmc_rank: 1, maturity_score: 80 }),
        },
        {
          listing_status: 'active',
          exchange: coinbase,
          project: project({ id: 'ethereum', slug: 'ethereum', name: 'Ethereum', cmc_rank: 2, maturity_score: 70 }),
        },
      ],
    })

    expect(aggregates).toEqual([
      expect.objectContaining({
        slug: 'coinbase',
        name: 'Coinbase',
        listedProjectCount: 2,
      }),
    ])
  })

  it('sorts non-Top-30 exchanges by BCE Exchange Score before listing count', () => {
    const aggregates = buildExchangeAggregates({
      exchanges: [alpha, beta],
      listings: [
        {
          listing_status: 'active',
          exchange: alpha,
          project: project({ id: 'alpha-core', slug: 'alpha-core', name: 'Alpha Core', cmc_rank: 10, maturity_score: 90 }),
        },
        {
          listing_status: 'active',
          exchange: beta,
          project: project({ id: 'beta-tail-1', slug: 'beta-tail-1', name: 'Beta Tail 1', cmc_rank: 4000, maturity_score: 40 }),
        },
        {
          listing_status: 'active',
          exchange: beta,
          project: project({ id: 'beta-tail-2', slug: 'beta-tail-2', name: 'Beta Tail 2', cmc_rank: null, maturity_score: null }),
        },
      ],
    })

    expect(aggregates.map((exchange) => exchange.slug)).toEqual(['alpha', 'beta'])
    expect(aggregates[0].bceExchangeScore).toBeGreaterThan(aggregates[1].bceExchangeScore ?? 0)
    expect(aggregates[0].listedProjectCount).toBeLessThan(aggregates[1].listedProjectCount)
  })

  it('returns listed project rows for a slug or exact name match', () => {
    const detail = buildExchangeProjectRows(rows, 'Binance')

    expect(detail.exchange?.slug).toBe('binance')
    expect(detail.projects).toEqual([
      expect.objectContaining({
        rank: 1,
        slug: 'bitcoin',
        cmcRank: 1,
        score: 80,
        reportTypes: ['econ'],
      }),
      expect.objectContaining({
        rank: 2,
        slug: 'ethereum',
        cmcRank: 2,
        score: null,
        reportTypes: [],
      }),
    ])
  })

  it('uses live localized report availability when it is provided', () => {
    const detail = buildExchangeProjectRows(rows, 'Binance', new Map([
      ['bitcoin', {
        reportTypes: ['econ', 'maturity'],
        reportDates: {
          econ: '2026-06-10T00:00:00Z',
          maturity: '2026-06-11T00:00:00Z',
          forensic: null,
        },
      }],
      ['ethereum', {
        reportTypes: [],
        reportDates: { econ: null, maturity: null, forensic: null },
      }],
    ]))

    expect(detail.projects).toEqual([
      expect.objectContaining({
        slug: 'bitcoin',
        reportTypes: ['econ', 'maturity'],
        reportDates: expect.objectContaining({
          econ: '2026-06-10T00:00:00Z',
          maturity: '2026-06-11T00:00:00Z',
        }),
      }),
      expect.objectContaining({
        slug: 'ethereum',
        reportTypes: [],
      }),
    ])
  })

  it('keeps report badges for exchange-listed projects outside the Top500 universe', () => {
    const openGradient = project({
      id: 'opengradient-id',
      slug: 'opengradient',
      name: 'OpenGradient',
      symbol: 'OG',
      cmc_rank: 577,
      market_cap_usd: 12,
      maturity_score: null,
    })
    const availabilityByProjectId = new Map([
      [openGradient.id, {
        reportTypes: ['econ'],
        reportDates: {
          econ: '2026-06-16T00:00:00Z',
          maturity: null,
          forensic: null,
        },
      }],
    ])

    const detail = buildExchangeProjectRows([
      {
        listing_status: 'active',
        exchange: binance,
        project: openGradient,
      },
    ], 'binance', availabilityByProjectId)

    expect(detail.projects).toEqual([
      expect.objectContaining({
        slug: 'opengradient',
        rank: 577,
        cmcRank: 577,
        reportTypes: ['econ'],
        reportDates: expect.objectContaining({
          econ: '2026-06-16T00:00:00Z',
        }),
      }),
    ])
  })

  it('applies only CMC market data matched by project market-data aliases', () => {
    const openGradient = project({
      id: 'opengradient-id',
      slug: 'opengradient',
      name: 'OpenGradient',
      symbol: 'OG',
      coingecko_id: 'open-gradient',
      cmc_id: 'opengradient',
      market_cap_usd: 12,
      maturity_score: null,
    })
    const exchangeRows: ExchangeListingRecord[] = [
      {
        listing_status: 'active',
        exchange: binance,
        project: openGradient,
      },
    ]

    const rankedRows = applyLatestCmcRanks(exchangeRows, new Map([
      ['open-gradient', { cmcRank: 577, marketCap: 123456789 }],
    ]))
    const detail = buildExchangeProjectRows(rankedRows, 'binance')

    expect(detail.projects).toEqual([
      expect.objectContaining({
        slug: 'opengradient',
        rank: 577,
        cmcRank: 577,
        marketCap: 123456789,
      }),
    ])
  })

  it('applies latest CMC ranks through tracked project aliases', () => {
    const midnight = project({
      id: 'midnight-id',
      slug: 'midnight',
      name: 'Midnight',
      symbol: 'NIGHT',
      coingecko_id: 'midnight-3',
      aliases: ['midnight-network'],
      market_cap_usd: 618692537,
      maturity_score: null,
    })
    const exchangeRows: ExchangeListingRecord[] = [
      {
        listing_status: 'active',
        exchange: bybit,
        project: midnight,
      },
    ]

    expect(getMissingProjectMarketDataKeys(exchangeRows, new Map())).toEqual([
      'midnight',
      'midnight-3',
      'midnight-network',
    ])

    const rankedRows = applyLatestCmcRanks(exchangeRows, new Map([
      ['midnight-network', { cmcRank: 79, marketCap: 506721371 }],
    ]))
    const detail = buildExchangeProjectRows(rankedRows, 'bybit')

    expect(detail.projects).toEqual([
      expect.objectContaining({
        slug: 'midnight',
        rank: 79,
        cmcRank: 79,
        marketCap: 506721371,
      }),
    ])
    expect(getMissingProjectMarketDataKeys(rankedRows, new Map([
      ['midnight-network', { cmcRank: 79, marketCap: 506721371 }],
    ]))).toEqual([])
  })

  it('keeps unranked exchange rows unranked instead of assigning row order', () => {
    const unranked = project({
      id: 'unranked-id',
      slug: 'unranked-lab',
      name: 'Unranked Lab',
      symbol: 'UNR',
      cmc_rank: null,
      market_cap_usd: 999,
    })

    const detail = buildExchangeProjectRows([
      {
        listing_status: 'active',
        exchange: binance,
        project: unranked,
      },
    ], 'binance')

    expect(detail.projects).toEqual([
      expect.objectContaining({
        slug: 'unranked-lab',
        rank: null,
        cmcRank: null,
      }),
    ])
  })

  it('identifies exchange listing market-data keys missing from the latest rank snapshot', () => {
    const openGradient = project({
      id: 'opengradient-id',
      slug: 'opengradient',
      name: 'OpenGradient',
      symbol: 'OG',
      coingecko_id: 'open-gradient',
      cmc_id: 'opengradient-cmc',
    })
    const exchangeRows: ExchangeListingRecord[] = [
      {
        listing_status: 'active',
        exchange: binance,
        project: openGradient,
      },
    ]

    expect(getMissingProjectMarketDataKeys(exchangeRows, new Map())).toEqual([
      'opengradient',
      'open-gradient',
      'opengradient-cmc',
    ])

    expect(getMissingProjectMarketDataKeys(exchangeRows, new Map([
      ['open-gradient', { cmcRank: 577, marketCap: 123456789 }],
    ]))).toEqual([])
  })

  it('keeps long-tail report badges across non-Binance exchange detail rows', () => {
    const okxTail = project({
      id: 'okx-tail-id',
      slug: 'okx-tail-lab',
      name: 'OKX Tail Lab',
      symbol: 'OTL',
      cmc_rank: 1201,
      market_cap_usd: 30,
      maturity_score: null,
    })
    const bybitTail = project({
      id: 'bybit-tail-id',
      slug: 'bybit-tail-lab',
      name: 'Bybit Tail Lab',
      symbol: 'BTL',
      cmc_rank: null,
      market_cap_usd: 20,
      maturity_score: null,
    })
    const coinbaseTail = project({
      id: 'coinbase-tail-id',
      slug: 'coinbase-tail-lab',
      name: 'Coinbase Tail Lab',
      symbol: 'CTL',
      cmc_rank: 777,
      market_cap_usd: 10,
      maturity_score: null,
    })
    const exchangeRows: ExchangeListingRecord[] = [
      { listing_status: 'active', exchange: okx, project: okxTail },
      { listing_status: 'active', exchange: bybit, project: bybitTail },
      { listing_status: 'active', exchange: coinbase, project: coinbaseTail },
    ]
    const availabilityByProjectId = new Map([
      [okxTail.id, {
        reportTypes: ['econ'],
        reportDates: {
          econ: '2026-06-16T01:00:00Z',
          maturity: null,
          forensic: null,
        },
      }],
      [bybitTail.id, {
        reportTypes: ['maturity'],
        reportDates: {
          econ: null,
          maturity: '2026-06-16T02:00:00Z',
          forensic: null,
        },
      }],
      [coinbaseTail.id, {
        reportTypes: ['forensic'],
        reportDates: {
          econ: null,
          maturity: null,
          forensic: '2026-06-16T03:00:00Z',
        },
      }],
    ])

    expect(buildExchangeProjectRows(exchangeRows, 'okx', availabilityByProjectId).projects).toEqual([
      expect.objectContaining({
        name: 'OKX Tail Lab',
        symbol: 'OTL',
        slug: 'okx-tail-lab',
        score: null,
        reportTypes: ['econ'],
        reportDates: expect.objectContaining({ econ: '2026-06-16T01:00:00Z' }),
      }),
    ])
    expect(buildExchangeProjectRows(exchangeRows, 'bybit', availabilityByProjectId).projects).toEqual([
      expect.objectContaining({
        name: 'Bybit Tail Lab',
        symbol: 'BTL',
        slug: 'bybit-tail-lab',
        score: null,
        reportTypes: ['maturity'],
        reportDates: expect.objectContaining({ maturity: '2026-06-16T02:00:00Z' }),
      }),
    ])
    expect(buildExchangeProjectRows(exchangeRows, 'coinbase', availabilityByProjectId).projects).toEqual([
      expect.objectContaining({
        name: 'Coinbase Tail Lab',
        symbol: 'CTL',
        slug: 'coinbase-tail-lab',
        score: null,
        reportTypes: ['forensic'],
        reportDates: expect.objectContaining({ forensic: '2026-06-16T03:00:00Z' }),
      }),
    ])
  })

  it('shows the same long-tail report availability on every exchange listing for a project', () => {
    const sharedTail = project({
      id: 'shared-tail-id',
      slug: 'shared-tail-lab',
      name: 'Shared Tail Lab',
      symbol: 'STL',
      cmc_rank: 5001,
      market_cap_usd: 5,
      maturity_score: null,
    })
    const exchangeRows: ExchangeListingRecord[] = [
      { listing_status: 'active', exchange: binance, project: sharedTail },
      { listing_status: 'active', exchange: okx, project: sharedTail },
    ]
    const availabilityByProjectId = new Map([
      [sharedTail.id, {
        reportTypes: ['econ', 'maturity'],
        reportDates: {
          econ: '2026-06-16T04:00:00Z',
          maturity: '2026-06-16T05:00:00Z',
          forensic: null,
        },
      }],
    ])

    for (const exchangeSlug of ['binance', 'okx']) {
      expect(buildExchangeProjectRows(exchangeRows, exchangeSlug, availabilityByProjectId).projects).toEqual([
        expect.objectContaining({
          slug: 'shared-tail-lab',
          reportTypes: ['econ', 'maturity'],
          reportDates: expect.objectContaining({
            econ: '2026-06-16T04:00:00Z',
            maturity: '2026-06-16T05:00:00Z',
          }),
        }),
      ])
    }
  })

  it('maps canonical report availability to exchange listing aliases', () => {
    const nearListing = project({
      id: 'near-market-row',
      slug: 'near',
      name: 'NEAR Protocol',
      symbol: 'NEAR',
    })
    const nearReportProject = project({
      id: 'near-report-row',
      slug: 'near-protocol',
      name: 'NEAR Protocol',
      symbol: 'NEAR',
      status: 'monitoring_only',
      last_econ_report_at: '2026-06-11T03:35:01Z',
      last_maturity_report_at: '2026-06-11T03:02:41Z',
    })
    const availabilityByProjectId = new Map([
      [nearReportProject.id, {
        reportTypes: ['econ', 'maturity'],
        reportDates: {
          econ: '2026-06-11T03:35:01Z',
          maturity: '2026-06-11T03:02:41Z',
          forensic: null,
        },
      }],
    ])

    applyProjectReportAvailabilityAliases(
      availabilityByProjectId,
      [nearListing],
      [nearListing, nearReportProject],
    )

    const detail = buildExchangeProjectRows([
      {
        listing_status: 'active',
        exchange: binance,
        project: nearListing,
      },
    ], 'binance', availabilityByProjectId)

    expect(detail.projects[0]).toEqual(expect.objectContaining({
      slug: 'near',
      reportTypes: ['econ', 'maturity'],
      reportDates: expect.objectContaining({
        econ: '2026-06-11T03:35:01Z',
        maturity: '2026-06-11T03:02:41Z',
      }),
    }))
  })

  it('matches CMC aliases against internal exchange slugs', () => {
    const detail = buildExchangeProjectRows([
      {
        listing_status: 'active',
        exchange: {
          id: 'exchange-coinbase',
          slug: 'coinbase',
          name: 'Coinbase Exchange',
          status: 'active',
          website_url: null,
          country: 'US',
        },
        project: project({ id: 'bitcoin', slug: 'bitcoin', name: 'Bitcoin', maturity_score: 80 }),
      },
    ], 'gdax')

    expect(detail.exchange?.slug).toBe('coinbase')
    expect(detail.projects).toHaveLength(1)
  })

  it('keeps legacy gdax detail compatibility while preferring the canonical Coinbase exchange row', () => {
    const detail = buildExchangeProjectRows([
      {
        listing_status: 'active',
        exchange: legacyGdax,
        project: project({ id: 'bitcoin', slug: 'bitcoin', name: 'Bitcoin', maturity_score: 80 }),
      },
      {
        listing_status: 'active',
        exchange: coinbase,
        project: project({ id: 'bitcoin', slug: 'bitcoin', name: 'Bitcoin', maturity_score: 80 }),
      },
    ], 'gdax')

    expect(detail.exchange?.slug).toBe('coinbase')
    expect(detail.projects).toEqual([
      expect.objectContaining({ slug: 'bitcoin' }),
    ])
  })

  it('normalizes Coinbase source identifier variants to the same canonical detail row', () => {
    const detail = buildExchangeProjectRows([
      {
        listing_status: 'active',
        exchange: legacyGdax,
        project: project({ id: 'bitcoin', slug: 'bitcoin', name: 'Bitcoin', maturity_score: 80 }),
      },
      {
        listing_status: 'active',
        exchange: coinbase,
        project: project({ id: 'ethereum', slug: 'ethereum', name: 'Ethereum', maturity_score: 70 }),
      },
    ], 'coinbase_exchange')

    expect(detail.exchange?.slug).toBe('coinbase')
    expect(detail.projects.map((row) => row.slug)).toEqual(['bitcoin', 'ethereum'])
  })
})
