import {
  buildReportAvailabilityByProjectId,
  buildTrackedProjectLookup,
  canonicalSnapshotRowsToScoreRows,
  fetchVisibleReportsForScoreboard,
  hasCompleteCmcCanonicalTop200Snapshot,
  mergeScoreboardProjects,
  MIN_CMC_CANONICAL_TOP_200_SNAPSHOT_ROWS,
  snapshotRowsToScoreRows,
} from './page'

function makeSnapshotRow(rank: number, slug = `cmc-project-${rank}`) {
  return {
    slug,
    price_usd: rank,
    market_cap: 1_000_000 - rank,
    change_24h: 0,
    recorded_at: '2026-05-12',
    cmc_rank: rank,
  }
}

jest.mock('next-intl/server', () => ({
  getTranslations: jest.fn(),
}))

jest.mock('@/lib/supabase-server', () => ({
  createServerSupabaseClient: jest.fn(),
}))

jest.mock('@/lib/repositories/projects', () => ({
  createProjectsRepository: jest.fn(),
}))

jest.mock('@/components/ScoreTableGate', () => function ScoreTableGate() {
  return null
})

jest.mock('@/components/SubscribeForm', () => function SubscribeForm() {
  return null
})

describe('score page CMC canonical Top 200 snapshot guard', () => {
  it('rejects partial snapshots as non-canonical Top 200 data', () => {
    expect(hasCompleteCmcCanonicalTop200Snapshot([makeSnapshotRow(1)])).toBe(false)
    expect(hasCompleteCmcCanonicalTop200Snapshot(
      Array.from({ length: 199 }, (_, index) => makeSnapshotRow(index + 1)),
    )).toBe(false)
  })

  it('rejects 200-row snapshots without canonical CMC ranks', () => {
    const rowsWithoutCmcRank = Array.from({ length: 200 }, (_, index) => ({
      ...makeSnapshotRow(index + 1),
      cmc_rank: null,
    }))

    expect(hasCompleteCmcCanonicalTop200Snapshot(rowsWithoutCmcRank)).toBe(false)
    expect(canonicalSnapshotRowsToScoreRows(rowsWithoutCmcRank, [])).toEqual([])
  })

  it('accepts only snapshots with contiguous CMC ranks 1 through 200', () => {
    const canonicalRows = Array.from(
      { length: MIN_CMC_CANONICAL_TOP_200_SNAPSHOT_ROWS },
      (_, index) => makeSnapshotRow(index + 1),
    )
    const duplicateRankRows = canonicalRows.map((row, index) => (
      index === 199 ? { ...row, cmc_rank: 199 } : row
    ))

    expect(hasCompleteCmcCanonicalTop200Snapshot(canonicalRows)).toBe(true)
    expect(hasCompleteCmcCanonicalTop200Snapshot(duplicateRankRows)).toBe(false)
  })

  it('does not substitute tracked projects when the CMC snapshot is incomplete', () => {
    const trackedProjects = [
      {
        id: 'htx-project',
        name: 'HTX',
        slug: 'htx',
        symbol: 'HTX',
        category: 'Exchange',
        market_cap_usd: 100,
        coingecko_id: 'htx',
        cmc_id: 'htx',
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const partialSnapshotRows = Array.from(
      { length: 199 },
      (_, index) => makeSnapshotRow(index + 1, index === 0 ? 'bitcoin' : `cmc-project-${index}`),
    )

    expect(canonicalSnapshotRowsToScoreRows(partialSnapshotRows, trackedProjects)).toEqual([])
  })

  it('uses CoinMarketCap identity for ranked row name and ticker display', () => {
    const trackedProjects = [
      {
        id: 'synthetix-project',
        name: 'Synthetics',
        slug: 'synthetix',
        symbol: 'S',
        category: 'DeFi',
        market_cap_usd: 100,
        coingecko_id: 'synthetix',
        cmc_id: 'synthetix',
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const [row] = snapshotRowsToScoreRows(
      [
        {
          ...makeSnapshotRow(190, 'synthetix'),
          cmc_symbol: 'SNX',
          cmc_name: 'Synthetix',
        },
      ],
      buildTrackedProjectLookup(trackedProjects),
    )

    expect(row).toMatchObject({
      name: 'Synthetix',
      symbol: 'SNX',
      slug: 'synthetix',
    })
  })

  it('excludes rows outside the canonical CMC Top 200 before rendering', () => {
    const snapshotRows = [
      ...Array.from({ length: 200 }, (_, index) => makeSnapshotRow(index + 1)),
      makeSnapshotRow(201, 'rain'),
      makeSnapshotRow(203, 'htx'),
    ].reverse()

    const rows = canonicalSnapshotRowsToScoreRows(snapshotRows, [])

    expect(rows).toHaveLength(200)
    expect(rows[0]).toMatchObject({ rank: 1, slug: 'cmc-project-1' })
    expect(rows[199]).toMatchObject({ rank: 200, slug: 'cmc-project-200' })
    expect(rows.map((row) => row.slug)).not.toContain('rain')
    expect(rows.map((row) => row.slug)).not.toContain('htx')
  })

  it('does not let operational project aliases replace canonical CMC snapshot identities', () => {
    const trackedProjects = [
      {
        id: 'irys-project',
        name: 'Irys',
        slug: 'irys',
        symbol: 'IRYS',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: 'irys',
        cmc_id: null,
        aliases: ['cmc-project-150'],
        maturity_score: null,
        last_econ_report_at: '2026-05-27T00:00:00.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = Array.from(
      { length: 200 },
      (_, index) => makeSnapshotRow(index + 1),
    )

    const rows = canonicalSnapshotRowsToScoreRows(snapshotRows, trackedProjects)

    expect(rows[149]).toMatchObject({
      rank: 150,
      name: 'Cmc Project 150',
      slug: 'cmc-project-150',
      reportTypes: [],
    })
    expect(rows.map((row) => row.slug)).not.toContain('irys')
  })

  it('uses CMC identity to recover report-bearing projects when the CMC slug differs', () => {
    const trackedProjects = [
      {
        id: 'instadapp-project',
        name: 'Fluid',
        slug: 'instadapp',
        symbol: 'FLUID',
        category: 'DeFi',
        market_cap_usd: 100,
        coingecko_id: 'instadapp',
        cmc_id: null,
        aliases: ['fluid', 'fluid protocol'],
        maturity_score: null,
        last_econ_report_at: '2026-05-29T00:00:00.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = Array.from(
      { length: 200 },
      (_, index) => ({
        ...makeSnapshotRow(index + 1, index === 155 ? 'fluid-protocol' : `cmc-project-${index + 1}`),
        cmc_name: index === 155 ? 'Fluid' : `CMC Project ${index + 1}`,
        cmc_symbol: index === 155 ? 'FLUID' : `P${index + 1}`,
      }),
    )

    const rows = canonicalSnapshotRowsToScoreRows(snapshotRows, trackedProjects)

    expect(rows[155]).toMatchObject({
      rank: 156,
      name: 'Fluid',
      symbol: 'FLUID',
      slug: 'instadapp',
      reportTypes: ['econ'],
    })
  })

  it('still applies explicit scoreboard canonical aliases for CMC snapshot rows', () => {
    const trackedProjects = [
      {
        id: 'ethena-project',
        name: 'Ethena',
        slug: 'ethena',
        symbol: 'ENA',
        category: 'Stablecoins',
        market_cap_usd: 100,
        coingecko_id: 'ethena',
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-01T00:00:00.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = Array.from(
      { length: 200 },
      (_, index) => makeSnapshotRow(index + 1, index === 36 ? 'ethena-usde' : `cmc-project-${index + 1}`),
    )

    const rows = canonicalSnapshotRowsToScoreRows(snapshotRows, trackedProjects)

    expect(rows[36]).toMatchObject({
      rank: 37,
      name: 'Ethena',
      slug: 'ethena',
      reportTypes: ['econ'],
    })
  })

  it('uses supplemental canonical alias targets when a CMC row has a separate market project', () => {
    const activeMarketProjects = [
      {
        id: 'ethgas-market-project',
        name: 'ETHGas',
        slug: 'ethgas',
        symbol: 'GWEI',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: 'ethgas',
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const reportBearingAliasTargets = [
      {
        id: 'eth-gas-project',
        name: 'ETHGas',
        slug: 'eth-gas',
        symbol: 'GWEI',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-28T18:28:12.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = Array.from(
      { length: 200 },
      (_, index) => makeSnapshotRow(index + 1, index === 142 ? 'ethgas' : `cmc-project-${index + 1}`),
    )

    const rows = canonicalSnapshotRowsToScoreRows(
      snapshotRows,
      mergeScoreboardProjects(activeMarketProjects, reportBearingAliasTargets),
    )

    expect(rows[142]).toMatchObject({
      rank: 143,
      name: 'ETHGas',
      symbol: 'GWEI',
      slug: 'eth-gas',
      reportTypes: ['econ'],
    })
  })

  it('uses canonical alias target report availability when CMC identifies ETHGas by GWEI', () => {
    const activeMarketProjects = [
      {
        id: 'ethgas-market-project',
        name: 'ETHGas',
        slug: 'ethgas',
        symbol: 'GWEI',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: 'ethgas',
        cmc_id: 'gwei',
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const availabilityByProjectSlug = new Map([
      ['eth-gas', {
        reportTypes: ['econ'],
        reportDates: {
          econ: '2026-05-28T18:28:12.000Z',
          maturity: null,
          forensic: null,
        },
      }],
    ])
    const snapshotRows = Array.from(
      { length: 200 },
      (_, index) => makeSnapshotRow(index + 1, index === 142 ? 'gwei' : `cmc-project-${index + 1}`),
    )

    const rows = canonicalSnapshotRowsToScoreRows(
      snapshotRows,
      activeMarketProjects,
      undefined,
      availabilityByProjectSlug,
    )

    expect(rows[142]).toMatchObject({
      rank: 143,
      name: 'ETHGas',
      symbol: 'GWEI',
      slug: 'eth-gas',
      reportTypes: ['econ'],
      reportDates: {
        econ: '2026-05-28T18:28:12.000Z',
      },
    })
  })
})

describe('score page tracked project aliases', () => {
  it('maps an Ethena USDe market snapshot row to the canonical Ethena project reports', () => {
    const trackedProjects = [
      {
        id: 'ethena-project',
        name: 'Ethena',
        slug: 'ethena',
        symbol: 'ENA',
        category: 'Stablecoins',
        market_cap_usd: 100,
        coingecko_id: 'ethena',
        cmc_id: 'ethena',
        aliases: ['ethena-usde', 'usde'],
        maturity_score: 81,
        last_econ_report_at: '2026-05-01T00:00:00.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [
      {
        slug: 'ethena-usde',
        price_usd: 1,
        market_cap: 500,
        change_24h: 0.1,
        recorded_at: '2026-05-03',
        cmc_rank: 37,
      },
    ]

    const lookup = buildTrackedProjectLookup(trackedProjects)
    const [row] = snapshotRowsToScoreRows(snapshotRows, lookup)

    expect(row).toMatchObject({
      name: 'Ethena',
      symbol: 'ENA',
      slug: 'ethena',
      reportTypes: ['econ'],
      reportDates: {
        econ: '2026-05-01T00:00:00.000Z',
      },
    })
  })

  it('keeps the Ethena USDe mapping when DB aliases are temporarily absent', () => {
    const trackedProjects = [
      {
        id: 'ethena-project',
        name: 'Ethena',
        slug: 'ethena',
        symbol: 'ENA',
        category: 'Stablecoins',
        market_cap_usd: 100,
        coingecko_id: 'ethena',
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-01T00:00:00.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [
      {
        slug: 'ethena-usde',
        price_usd: 1,
        market_cap: 500,
        change_24h: 0.1,
        recorded_at: '2026-05-03',
        cmc_rank: 37,
      },
    ]

    const lookup = buildTrackedProjectLookup(trackedProjects)
    const [row] = snapshotRowsToScoreRows(snapshotRows, lookup)

    expect(row).toMatchObject({
      name: 'Ethena',
      symbol: 'ENA',
      slug: 'ethena',
      reportTypes: ['econ'],
    })
  })

  it('lets canonical aliases override a lower-quality tracked alias row', () => {
    const trackedProjects = [
      {
        id: 'usde-row',
        name: 'Ethena USDe',
        slug: 'ethena-usde',
        symbol: 'USDE',
        category: '',
        market_cap_usd: 500,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'ethena-project',
        name: 'Ethena',
        slug: 'ethena',
        symbol: 'ENA',
        category: 'Stablecoins',
        market_cap_usd: 100,
        coingecko_id: 'ethena',
        cmc_id: null,
        aliases: ['ethena-usde', 'usde'],
        maturity_score: null,
        last_econ_report_at: '2026-05-01T00:00:00.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [
      {
        slug: 'ethena-usde',
        price_usd: 1,
        market_cap: 500,
        change_24h: 0.1,
        recorded_at: '2026-05-03',
        cmc_rank: 37,
      },
    ]

    const lookup = buildTrackedProjectLookup(trackedProjects)
    const [row] = snapshotRowsToScoreRows(snapshotRows, lookup)

    expect(row).toMatchObject({
      name: 'Ethena',
      symbol: 'ENA',
      slug: 'ethena',
      reportTypes: ['econ'],
    })
  })

  it('maps CMC market slugs to report-bearing canonical projects for ECON badges', () => {
    const trackedProjects = [
      {
        id: 'sei-project',
        name: 'Sei',
        slug: 'sei',
        symbol: 'SEI',
        category: 'L1',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-16T09:28:23.671777Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'pancakeswap-project',
        name: 'PancakeSwap',
        slug: 'pancakeswap',
        symbol: 'CAKE',
        category: 'DEX',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-16T10:32:06.905923Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'injective-project',
        name: 'Injective',
        slug: 'injective',
        symbol: 'INJ',
        category: 'L1',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-16T09:46:57.158395Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'curve-project',
        name: 'Curve DAO',
        slug: 'curve-dao',
        symbol: 'CRV',
        category: 'DEX',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-16T09:25:39.814357Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'wlfi-project',
        name: 'World Liberty Financial',
        slug: 'world-liberty-financial',
        symbol: 'WLFI',
        category: 'DeFi',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-14T11:38:00.204Z',
        last_maturity_report_at: '2026-05-16T20:44:55.034Z',
        last_forensic_report_at: null,
      },
      {
        id: 'eth-gas-project',
        name: 'ETHGas',
        slug: 'eth-gas',
        symbol: 'GWEI',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-28T18:28:12.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [
      makeSnapshotRow(89, 'sei-network'),
      makeSnapshotRow(90, 'pancakeswap-token'),
      makeSnapshotRow(95, 'injective-protocol'),
      makeSnapshotRow(100, 'curve-dao-token'),
      makeSnapshotRow(38, 'world-liberty-financial-wlfi'),
      makeSnapshotRow(143, 'ethgas'),
    ]

    const rows = snapshotRowsToScoreRows(snapshotRows, buildTrackedProjectLookup(trackedProjects))

    expect(rows.map((row) => ({
      name: row.name,
      slug: row.slug,
      reportTypes: row.reportTypes,
    }))).toEqual([
      { name: 'Sei', slug: 'sei', reportTypes: ['econ'] },
      { name: 'PancakeSwap', slug: 'pancakeswap', reportTypes: ['econ'] },
      { name: 'Injective', slug: 'injective', reportTypes: ['econ'] },
      { name: 'Curve DAO', slug: 'curve-dao', reportTypes: ['econ'] },
      { name: 'World Liberty Financial', slug: 'world-liberty-financial', reportTypes: ['econ', 'maturity'] },
      { name: 'ETHGas', slug: 'eth-gas', reportTypes: ['econ'] },
    ])
  })

  it('maps Genius market rows to the report-bearing Genius Terminal project', () => {
    const trackedProjects = [
      {
        id: 'genius-empty-project',
        name: 'Genius',
        slug: 'genius',
        symbol: 'GENIUS',
        category: 'AI',
        market_cap_usd: 186,
        coingecko_id: 'genius-3',
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'genius-terminal-project',
        name: 'Genius Terminal',
        slug: 'genius-terminal',
        symbol: 'GENIUS',
        category: 'AI',
        market_cap_usd: 186,
        coingecko_id: null,
        cmc_id: '39841',
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-25T00:00:00.000Z',
        last_maturity_report_at: '2026-05-25T01:00:00.000Z',
        last_forensic_report_at: null,
      },
    ]

    const [row] = snapshotRowsToScoreRows(
      [makeSnapshotRow(152, 'genius-3')],
      buildTrackedProjectLookup(trackedProjects),
    )

    expect(row).toMatchObject({
      name: 'Genius Terminal',
      slug: 'genius-terminal',
      reportTypes: ['econ', 'maturity'],
    })
  })

  it('does not show timestamp-only report badges when live report availability was loaded', () => {
    const trackedProjects = [
      {
        id: 'bitcoin-project',
        name: 'Bitcoin',
        slug: 'bitcoin',
        symbol: 'BTC',
        category: 'L1',
        market_cap_usd: 100,
        coingecko_id: 'bitcoin',
        cmc_id: 'bitcoin',
        aliases: [],
        maturity_score: null,
        last_econ_report_at: '2026-05-08T13:39:29.458217Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [
      {
        slug: 'bitcoin',
        price_usd: 100000,
        market_cap: 100,
        change_24h: 0.1,
        recorded_at: '2026-05-08',
        cmc_rank: 1,
      },
    ]

    const lookup = buildTrackedProjectLookup(trackedProjects)
    const [row] = snapshotRowsToScoreRows(snapshotRows, lookup, new Map())

    expect(row).toMatchObject({
      name: 'Bitcoin',
      symbol: 'BTC',
      slug: 'bitcoin',
      reportTypes: [],
      reportDates: {
        econ: null,
        maturity: null,
        forensic: null,
      },
    })
  })
})

describe('score page report availability policy', () => {
  it('uses the injected server-side report client when reading scoreboard availability', async () => {
    const query = {
      select: jest.fn().mockReturnThis(),
      in: jest.fn().mockReturnThis(),
      then: undefined,
    }
    query.in
      .mockReturnValueOnce(query)
      .mockReturnValueOnce(query)
      .mockResolvedValueOnce({
        data: [
          {
            project_id: 'bitcoin-project',
            report_type: 'econ',
            language: 'ko',
            published_at: '2026-05-01T00:00:00.000Z',
            gdrive_urls_by_lang: {
              ko: { url: 'https://drive.google.com/file/d/bitcoin-ko/view' },
            },
          },
        ],
        error: null,
      })
    const reportSupabase = {
      from: jest.fn().mockReturnValue(query),
    }

    const result = await fetchVisibleReportsForScoreboard(
      ['bitcoin-project'],
      reportSupabase as never,
    )

    expect(reportSupabase.from).toHaveBeenCalledWith('project_reports')
    expect(query.in).toHaveBeenNthCalledWith(1, 'project_id', ['bitcoin-project'])
    expect(query.in).toHaveBeenNthCalledWith(2, 'report_type', ['econ', 'maturity', 'forensic'])
    expect(query.in).toHaveBeenNthCalledWith(3, 'status', ['published', 'coming_soon', 'in_review'])
    expect(result.loaded).toBe(true)
    expect(result.reports).toHaveLength(1)
  })

  it('counts PDF-only localized reports as available for scoreboard badges', () => {
    const availability = buildReportAvailabilityByProjectId([
      {
        project_id: 'dexe-project',
        report_type: 'econ',
        language: 'en',
        published_at: '2026-05-01T00:00:00.000Z',
        gdrive_urls_by_lang: {
          en: { url: 'https://drive.google.com/file/d/dexe-en/view' },
        },
        slide_html_urls_by_lang: null,
      },
    ], 'en')

    expect(availability.get('dexe-project')).toEqual({
      reportTypes: ['econ'],
      reportDates: {
        econ: '2026-05-01T00:00:00.000Z',
        maturity: null,
        forensic: null,
      },
    })
  })

  it('does not count reports without an asset for the requested locale', () => {
    const availability = buildReportAvailabilityByProjectId([
      {
        project_id: 'alpha-project',
        report_type: 'econ',
        language: 'zh',
        published_at: '2026-05-01T00:00:00.000Z',
        gdrive_urls_by_lang: {
          zh: { url: 'https://drive.google.com/file/d/alpha-zh/view' },
        },
        slide_html_urls_by_lang: null,
      },
    ], 'ko')

    expect(availability.has('alpha-project')).toBe(false)
  })

  it('renders active ECON availability for Bitcoin when a Korean localized asset exists', () => {
    const trackedProjects = [
      {
        id: 'bitcoin-project',
        name: 'Bitcoin',
        slug: 'bitcoin',
        symbol: 'BTC',
        category: 'L1',
        market_cap_usd: 100,
        coingecko_id: 'bitcoin',
        cmc_id: 'bitcoin',
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const availability = buildReportAvailabilityByProjectId([
      {
        project_id: 'bitcoin-project',
        report_type: 'econ',
        language: 'ko',
        published_at: '2026-05-01T00:00:00.000Z',
        gdrive_urls_by_lang: {
          ko: { url: 'https://drive.google.com/file/d/bitcoin-ko/view' },
        },
      },
    ], 'ko')

    const [row] = snapshotRowsToScoreRows(
      [makeSnapshotRow(1, 'bitcoin')],
      buildTrackedProjectLookup(trackedProjects),
      availability,
    )

    expect(row).toMatchObject({
      slug: 'bitcoin',
      reportTypes: ['econ'],
      reportDates: {
        econ: '2026-05-01T00:00:00.000Z',
      },
    })
  })

  it('renders active ECON availability for Aave when an English localized asset exists', () => {
    const trackedProjects = [
      {
        id: 'aave-project',
        name: 'Aave',
        slug: 'aave',
        symbol: 'AAVE',
        category: 'DeFi',
        market_cap_usd: 100,
        coingecko_id: 'aave',
        cmc_id: 'aave',
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const availability = buildReportAvailabilityByProjectId([
      {
        project_id: 'aave-project',
        report_type: 'econ',
        language: 'en',
        published_at: '2026-05-02T00:00:00.000Z',
        gdrive_urls_by_lang: {
          en: { url: 'https://drive.google.com/file/d/aave-en/view' },
        },
      },
    ], 'en')

    const [row] = snapshotRowsToScoreRows(
      [makeSnapshotRow(48, 'aave')],
      buildTrackedProjectLookup(trackedProjects),
      availability,
    )

    expect(row).toMatchObject({
      slug: 'aave',
      reportTypes: ['econ'],
      reportDates: {
        econ: '2026-05-02T00:00:00.000Z',
      },
    })
  })

  it('uses the latest localized report version for scoreboard badge dates', () => {
    const availability = buildReportAvailabilityByProjectId([
      {
        id: 'aave-econ-v1',
        project_id: 'aave-project',
        report_type: 'econ',
        version: 1,
        is_latest: false,
        language: 'en',
        published_at: '2026-05-10T00:00:00.000Z',
        gdrive_urls_by_lang: {
          en: { url: 'https://drive.google.com/file/d/aave-v1-en/view' },
        },
      },
      {
        id: 'aave-econ-v2',
        project_id: 'aave-project',
        report_type: 'econ',
        version: 2,
        is_latest: true,
        language: 'en',
        published_at: '2026-05-08T00:00:00.000Z',
        gdrive_urls_by_lang: {
          en: { url: 'https://drive.google.com/file/d/aave-v2-en/view' },
        },
      },
    ], 'en')

    expect(availability.get('aave-project')).toEqual({
      reportTypes: ['econ'],
      reportDates: {
        econ: '2026-05-08T00:00:00.000Z',
        maturity: null,
        forensic: null,
      },
    })
  })

  it('uses the newest locale-supported report when a newer version lacks locale support', () => {
    const availability = buildReportAvailabilityByProjectId([
      {
        id: 'alpha-econ-v1-ko',
        project_id: 'alpha-project',
        report_type: 'econ',
        version: 1,
        is_latest: false,
        language: 'ko',
        published_at: '2026-05-10T00:00:00.000Z',
        gdrive_urls_by_lang: {
          ko: { url: 'https://drive.google.com/file/d/alpha-v1-ko/view' },
        },
      },
      {
        id: 'alpha-econ-v2-zh',
        project_id: 'alpha-project',
        report_type: 'econ',
        version: 2,
        is_latest: true,
        language: 'zh',
        published_at: '2026-05-11T00:00:00.000Z',
        gdrive_urls_by_lang: {
          zh: { url: 'https://drive.google.com/file/d/alpha-v2-zh/view' },
        },
      },
    ], 'ko')

    expect(availability.get('alpha-project')).toEqual({
      reportTypes: ['econ'],
      reportDates: {
        econ: '2026-05-10T00:00:00.000Z',
        maturity: null,
        forensic: null,
      },
    })
  })

  it('renders OKX ECON and MAT badges when localized assets exist', () => {
    const trackedProjects = [
      {
        id: 'okx-project',
        name: 'OKX',
        slug: 'okx',
        symbol: 'OKB',
        category: 'Exchange',
        market_cap_usd: 100,
        coingecko_id: 'okb',
        cmc_id: 'okb',
        aliases: ['okx'],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const availability = buildReportAvailabilityByProjectId([
      {
        project_id: 'okx-project',
        report_type: 'econ',
        language: 'ko',
        published_at: '2026-05-14T10:00:00.000Z',
        gdrive_urls_by_lang: {
          ko: { url: 'https://drive.google.com/file/d/okx-econ-ko/view' },
        },
      },
      {
        project_id: 'okx-project',
        report_type: 'maturity',
        language: 'ko',
        published_at: '2026-05-14T11:00:00.000Z',
        slide_html_urls_by_lang: {
          ko: 'https://www.bcelab.xyz/reports/okx/maturity',
        },
      },
    ], 'ko')

    const [row] = snapshotRowsToScoreRows(
      [makeSnapshotRow(39, 'okx')],
      buildTrackedProjectLookup(trackedProjects),
      availability,
    )

    expect(row).toMatchObject({
      slug: 'okx',
      reportTypes: ['econ', 'maturity'],
      reportDates: {
        econ: '2026-05-14T10:00:00.000Z',
        maturity: '2026-05-14T11:00:00.000Z',
      },
    })
  })
})
