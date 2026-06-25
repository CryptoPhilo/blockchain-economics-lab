import {
  applyLatestCmcRanks,
  applyProjectReportAvailabilityAliases,
  buildExchangeAggregates,
  buildExchangeProjectRows,
  calculateBceExchangeScore,
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

  it('suppresses CMC Top 30 exchanges when no listing rows match', () => {
    const aggregates = buildExchangeAggregates({
      exchanges: [bybit],
      listings: [],
    })

    expect(aggregates).toEqual([])
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

  it('returns Top500-compatible project rows for a slug or exact name match', () => {
    const detail = buildExchangeProjectRows(rows, 'Binance')

    expect(detail.exchange?.slug).toBe('binance')
    expect(detail.projects).toEqual([
      expect.objectContaining({
        rank: 1,
        cmcRank: 1,
        slug: 'bitcoin',
        score: 80,
        reportTypes: ['econ'],
      }),
      expect.objectContaining({
        rank: 2,
        cmcRank: 2,
        slug: 'ethereum',
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

  it('preserves tracked ECON/MAT fallback when live report availability is partial without reviving FOR fallback', () => {
    const bitcoin = project({
      id: 'bitcoin-project',
      slug: 'bitcoin',
      name: 'Bitcoin',
      symbol: 'BTC',
      market_cap_usd: 100,
      cmc_rank: 1,
      last_econ_report_at: '2026-05-01T00:00:00Z',
      last_maturity_report_at: '2026-05-02T00:00:00Z',
      last_forensic_report_at: '2026-05-03T00:00:00Z',
    })
    const detail = buildExchangeProjectRows([
      {
        listing_status: 'active',
        exchange: binance,
        project: bitcoin,
      },
    ], 'Binance', new Map([
      ['bitcoin-project', {
        reportTypes: ['econ'],
        reportDates: {
          econ: '2026-06-10T00:00:00Z',
          maturity: null,
          forensic: null,
        },
      }],
    ]))

    expect(detail.projects[0]).toEqual(expect.objectContaining({
      rank: 1,
      cmcRank: 1,
      slug: 'bitcoin',
      reportTypes: ['econ', 'maturity'],
      reportDates: expect.objectContaining({
        econ: '2026-06-10T00:00:00Z',
        maturity: '2026-05-02T00:00:00Z',
        forensic: null,
      }),
    }))
  })

  it('applies latest CMC ranks through project name and alias keys', () => {
    const polygonListing = project({
      id: 'polygon-listing',
      slug: 'matic-network',
      name: 'Polygon',
      symbol: 'POL',
      cmc_rank: null,
      aliases: ['polygon'],
    })

    const rankedRows = applyLatestCmcRanks([
      {
        listing_status: 'active',
        exchange: binance,
        project: polygonListing,
      },
    ], new Map([
      ['polygon', 63],
      ['polygon:pol', 63],
    ]))

    const detail = buildExchangeProjectRows(rankedRows, 'Binance')

    expect(detail.projects[0]).toEqual(expect.objectContaining({
      rank: 63,
      cmcRank: 63,
      slug: 'matic-network',
    }))
  })

  it('applies canonical CMC rank aliases for renamed projects', () => {
    const tonListing = project({
      id: 'ton-listing',
      slug: 'the-open-network',
      name: 'TON',
      symbol: 'TON',
      cmc_rank: null,
      aliases: null,
    })

    const rankedRows = applyLatestCmcRanks([
      {
        listing_status: 'active',
        exchange: binance,
        project: tonListing,
      },
    ], new Map([
      ['toncoin', 23],
    ]))

    const detail = buildExchangeProjectRows(rankedRows, 'Binance')

    expect(detail.projects[0]).toEqual(expect.objectContaining({
      rank: 23,
      cmcRank: 23,
      slug: 'the-open-network',
    }))
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

  it('merges report availability from multiple alias-matched report projects', () => {
    const saharaListing = project({
      id: 'sahara-market-row',
      slug: 'sahara-ai',
      name: 'Sahara AI',
      symbol: 'SAHARA',
    })
    const saharaAnalysisProject = project({
      id: 'sahara-analysis-row',
      slug: 'sahara-ai',
      name: 'Sahara AI',
      symbol: 'SAHARA',
      status: 'monitoring_only',
    })
    const saharaForensicProject = project({
      id: 'sahara-forensic-row',
      slug: 'sahara-ai',
      name: 'Sahara AI',
      symbol: 'SAHARA',
      status: 'monitoring_only',
    })
    const availabilityByProjectId = new Map([
      [saharaAnalysisProject.id, {
        reportTypes: ['econ', 'maturity'],
        reportDates: {
          econ: '2026-05-29T00:00:00Z',
          maturity: '2026-06-09T00:00:00Z',
          forensic: null,
        },
      }],
      [saharaForensicProject.id, {
        reportTypes: ['forensic'],
        reportDates: {
          econ: null,
          maturity: null,
          forensic: '2026-06-05T00:00:00Z',
        },
      }],
    ])

    applyProjectReportAvailabilityAliases(
      availabilityByProjectId,
      [saharaListing],
      [saharaListing, saharaAnalysisProject, saharaForensicProject],
    )

    const detail = buildExchangeProjectRows([
      {
        listing_status: 'active',
        exchange: binance,
        project: saharaListing,
      },
    ], 'binance', availabilityByProjectId)

    expect(detail.projects[0]).toEqual(expect.objectContaining({
      slug: 'sahara-ai',
      reportTypes: ['econ', 'maturity', 'forensic'],
      reportDates: expect.objectContaining({
        econ: '2026-05-29T00:00:00Z',
        maturity: '2026-06-09T00:00:00Z',
        forensic: '2026-06-05T00:00:00Z',
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
