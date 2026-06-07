import {
  buildReportAvailabilityByProjectId,
  buildReportAvailabilityByProjectSlug,
  buildTrackedProjectLookup,
  canonicalSnapshotRowsToScoreRows,
  fetchVisibleReportsForScoreboard,
  hasCompleteCmcCanonicalTop500Snapshot,
  mergeScoreboardProjects,
  MIN_CMC_CANONICAL_TOP_500_SNAPSHOT_ROWS,
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

describe('score page CMC canonical Top 500 snapshot guard', () => {
  it('rejects partial snapshots as non-canonical Top 500 data', () => {
    expect(hasCompleteCmcCanonicalTop500Snapshot([makeSnapshotRow(1)])).toBe(false)
    expect(hasCompleteCmcCanonicalTop500Snapshot(
      Array.from({ length: 499 }, (_, index) => makeSnapshotRow(index + 1)),
    )).toBe(false)
  })

  it('rejects 500-row snapshots without canonical CMC ranks', () => {
    const rowsWithoutCmcRank = Array.from({ length: 500 }, (_, index) => ({
      ...makeSnapshotRow(index + 1),
      cmc_rank: null,
    }))

    expect(hasCompleteCmcCanonicalTop500Snapshot(rowsWithoutCmcRank)).toBe(false)
    expect(canonicalSnapshotRowsToScoreRows(rowsWithoutCmcRank, [])).toEqual([])
  })

  it('accepts only snapshots with contiguous CMC ranks 1 through 500', () => {
    const canonicalRows = Array.from(
      { length: MIN_CMC_CANONICAL_TOP_500_SNAPSHOT_ROWS },
      (_, index) => makeSnapshotRow(index + 1),
    )
    const duplicateRankRows = canonicalRows.map((row, index) => (
      index === 499 ? { ...row, cmc_rank: 499 } : row
    ))

    expect(hasCompleteCmcCanonicalTop500Snapshot(canonicalRows)).toBe(true)
    expect(hasCompleteCmcCanonicalTop500Snapshot(duplicateRankRows)).toBe(false)
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
      { length: 499 },
      (_, index) => makeSnapshotRow(index + 1, index === 0 ? 'bitcoin' : `cmc-project-${index}`),
    )

    expect(canonicalSnapshotRowsToScoreRows(partialSnapshotRows, trackedProjects)).toEqual([])
  })

  it('does not fall back to tracked project ordering when no canonical CMC snapshot is renderable', () => {
    const trackedProjects = [
      {
        id: 'bitcoin-project',
        name: 'Bitcoin',
        slug: 'bitcoin',
        symbol: 'BTC',
        category: 'Layer 1',
        market_cap_usd: 1_200_000_000_000,
        coingecko_id: 'bitcoin',
        cmc_id: 'bitcoin',
        aliases: [],
        maturity_score: 83,
        last_econ_report_at: '2026-05-01T00:00:00.000Z',
        last_maturity_report_at: '2026-05-02T00:00:00.000Z',
        last_forensic_report_at: '2026-05-03T00:00:00.000Z',
      },
      {
        id: 'ethereum-project',
        name: 'Ethereum',
        slug: 'ethereum',
        symbol: 'ETH',
        category: 'Layer 1',
        market_cap_usd: 190_000_000_000,
        coingecko_id: 'ethereum',
        cmc_id: 'ethereum',
        aliases: [],
        maturity_score: 92,
        last_econ_report_at: '2026-05-01T00:00:00.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]

    expect(canonicalSnapshotRowsToScoreRows([], trackedProjects)).toEqual([])
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

  it('excludes rows outside the canonical CMC Top 500 before rendering', () => {
    const snapshotRows = [
      ...Array.from({ length: 500 }, (_, index) => makeSnapshotRow(index + 1)),
      makeSnapshotRow(501, 'rain'),
      makeSnapshotRow(503, 'htx'),
    ].reverse()

    const rows = canonicalSnapshotRowsToScoreRows(snapshotRows, [])

    expect(rows).toHaveLength(500)
    expect(rows[0]).toMatchObject({ rank: 1, slug: 'cmc-project-1' })
    expect(rows[499]).toMatchObject({ rank: 500, slug: 'cmc-project-500' })
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
      { length: 500 },
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
      { length: 500 },
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
      { length: 500 },
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
      { length: 500 },
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
        maturityScore: null,
      }],
    ])
    const snapshotRows = Array.from(
      { length: 500 },
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

  it('uses CMC identity aliases before stale snapshot slugs for renamed market rows', () => {
    const trackedProjects = [
      {
        id: 'river-project',
        name: 'River',
        slug: 'river',
        symbol: 'RIVER',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: 'river',
        aliases: ['river protocol'],
        maturity_score: null,
        last_econ_report_at: '2026-05-30T06:00:00.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'newton-project',
        name: 'Newton',
        slug: 'newton',
        symbol: 'N',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'ab-chain-project',
        name: 'AB Chain',
        slug: 'ab-chain',
        symbol: 'AB',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: 'ab',
        aliases: ['ab', 'ab chain'],
        maturity_score: null,
        last_econ_report_at: '2026-05-30T07:00:00.000Z',
        last_maturity_report_at: '2026-05-30T07:05:00.000Z',
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = Array.from(
      { length: 500 },
      (_, index) => {
        if (index === 172) {
          return {
            ...makeSnapshotRow(173, 'river'),
            cmc_name: 'River',
            cmc_symbol: 'RIVER',
          }
        }
        if (index === 173) {
          return {
            ...makeSnapshotRow(174, 'newton'),
            cmc_name: 'AB',
            cmc_symbol: 'AB',
          }
        }
        return makeSnapshotRow(index + 1, `cmc-project-${index + 1}`)
      },
    )

    const rows = canonicalSnapshotRowsToScoreRows(snapshotRows, trackedProjects)

    expect(rows[172]).toMatchObject({
      rank: 173,
      name: 'River',
      symbol: 'RIVER',
      slug: 'river',
      reportTypes: ['econ'],
    })
    expect(rows[173]).toMatchObject({
      rank: 174,
      name: 'AB',
      symbol: 'AB',
      slug: 'ab-chain',
      reportTypes: ['econ', 'maturity'],
    })
  })

  it('prefers report-bearing duplicate tracked projects for canonical scoreboard rows', () => {
    const trackedProjects = [
      {
        id: 'river-market-shell',
        name: 'River',
        slug: 'river',
        symbol: 'RIVER',
        category: 'infrastructure',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: 'river',
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'river-report-project',
        name: 'River',
        slug: 'river',
        symbol: 'RIVER',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 46,
        last_econ_report_at: '2026-05-30T12:02:31.576246+00:00',
        last_maturity_report_at: '2026-05-30T12:03:10.455466+00:00',
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = Array.from(
      { length: 500 },
      (_, index) => ({
        ...makeSnapshotRow(index + 1, index === 172 ? 'river' : `cmc-project-${index + 1}`),
        cmc_name: index === 172 ? 'River' : `CMC Project ${index + 1}`,
        cmc_symbol: index === 172 ? 'RIVER' : `P${index + 1}`,
      }),
    )

    const rows = canonicalSnapshotRowsToScoreRows(snapshotRows, trackedProjects)

    expect(rows[172]).toMatchObject({
      rank: 173,
      name: 'River',
      symbol: 'RIVER',
      slug: 'river',
      score: 46,
      reportTypes: ['econ', 'maturity'],
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
        id: 'ether-fi-project',
        name: 'Ether.fi',
        slug: 'ether-fi',
        symbol: 'ETHFI',
        category: 'DeFi',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 67,
        last_econ_report_at: '2026-06-06T00:00:00.000Z',
        last_maturity_report_at: '2026-06-06T00:00:00.000Z',
        last_forensic_report_at: '2026-06-06T00:00:00.000Z',
      },
      {
        id: 'optimism-project',
        name: 'Optimism',
        slug: 'optimism',
        symbol: 'OP',
        category: 'Layer 2',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 78,
        last_econ_report_at: '2026-06-06T00:00:00.000Z',
        last_maturity_report_at: '2026-06-06T00:00:00.000Z',
        last_forensic_report_at: '2026-06-06T00:00:00.000Z',
      },
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
      {
        id: 'starknet-project',
        name: 'Starknet',
        slug: 'starknet',
        symbol: 'STRK',
        category: 'Layer 2',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 74,
        last_econ_report_at: '2026-05-31T07:38:51.000Z',
        last_maturity_report_at: '2026-05-31T07:45:29.000Z',
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [
      makeSnapshotRow(73, 'ether-fi-ethfi'),
      makeSnapshotRow(74, 'optimism-ethereum'),
      makeSnapshotRow(89, 'sei-network'),
      makeSnapshotRow(90, 'pancakeswap-token'),
      makeSnapshotRow(95, 'injective-protocol'),
      makeSnapshotRow(100, 'curve-dao-token'),
      makeSnapshotRow(38, 'world-liberty-financial-wlfi'),
      makeSnapshotRow(143, 'ethgas'),
      makeSnapshotRow(131, 'starknet-token'),
    ]

    const rows = snapshotRowsToScoreRows(snapshotRows, buildTrackedProjectLookup(trackedProjects))

    expect(rows.map((row) => ({
      name: row.name,
      slug: row.slug,
      reportTypes: row.reportTypes,
    }))).toEqual([
      { name: 'Ether.fi', slug: 'ether-fi', reportTypes: ['econ', 'maturity', 'forensic'] },
      { name: 'Optimism', slug: 'optimism', reportTypes: ['econ', 'maturity', 'forensic'] },
      { name: 'Sei', slug: 'sei', reportTypes: ['econ'] },
      { name: 'PancakeSwap', slug: 'pancakeswap', reportTypes: ['econ'] },
      { name: 'Injective', slug: 'injective', reportTypes: ['econ'] },
      { name: 'Curve DAO', slug: 'curve-dao', reportTypes: ['econ'] },
      { name: 'World Liberty Financial', slug: 'world-liberty-financial', reportTypes: ['econ', 'maturity'] },
      { name: 'ETHGas', slug: 'eth-gas', reportTypes: ['econ'] },
      { name: 'Starknet', slug: 'starknet', reportTypes: ['econ', 'maturity'] },
    ])
  })

  it('maps CMC Top 500 slugs to report-bearing canonical report slugs', () => {
    const trackedProjects = [
      {
        id: 'bnb-project',
        name: 'BNB',
        slug: 'binancecoin',
        symbol: 'BNB',
        category: 'Layer 1',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 83,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'ton-project',
        name: 'Toncoin',
        slug: 'the-open-network',
        symbol: 'TON',
        category: 'Layer 1',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 80,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'dai-project',
        name: 'Dai',
        slug: 'dai',
        symbol: 'DAI',
        category: 'Stablecoin',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 78,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'hedera-project',
        name: 'Hedera',
        slug: 'hedera-hashgraph',
        symbol: 'HBAR',
        category: 'Layer 1',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 78,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'pi-project',
        name: 'Pi',
        slug: 'pi-network',
        symbol: 'PI',
        category: 'Layer 1',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 70,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'worldcoin-project',
        name: 'Worldcoin',
        slug: 'worldcoin',
        symbol: 'WLD',
        category: 'Identity',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 72,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'gate-project',
        name: 'GateToken',
        slug: 'gate',
        symbol: 'GT',
        category: 'Exchange Token',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 69,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'flare-project',
        name: 'Flare',
        slug: 'flare-networks',
        symbol: 'FLR',
        category: 'Layer 1',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 68,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'usd1-project',
        name: 'World Liberty Financial USD',
        slug: 'usd1',
        symbol: 'USD1',
        category: 'Stablecoin',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: 60,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'maplestory-project',
        name: 'NEXPACE',
        slug: 'maplestory-universe',
        symbol: 'NXPC',
        category: 'Gaming',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: ['MapleStory Universe', 'MSU'],
        maturity_score: 64,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
      {
        id: 'awe-project',
        name: 'AWE',
        slug: 'awe-network',
        symbol: 'AWE',
        category: 'AI',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: ['AWE Network'],
        maturity_score: null,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
      {
        id: 'gas-project',
        name: 'Gas',
        slug: 'gas',
        symbol: 'GAS',
        category: 'Layer 1',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: ['Neo GAS'],
        maturity_score: 61,
        last_econ_report_at: '2026-05-30T00:00:00.000Z',
        last_maturity_report_at: '2026-05-30T00:00:00.000Z',
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [
      makeSnapshotRow(4, 'bnb'),
      makeSnapshotRow(19, 'multi-collateral-dai'),
      makeSnapshotRow(20, 'toncoin'),
      makeSnapshotRow(21, 'world-liberty-financial-usd'),
      makeSnapshotRow(23, 'hedera'),
      makeSnapshotRow(44, 'pi'),
      makeSnapshotRow(53, 'worldcoin-org'),
      makeSnapshotRow(66, 'gatetoken'),
      makeSnapshotRow(72, 'flare'),
      makeSnapshotRow(184, 'nexpace'),
      makeSnapshotRow(196, 'awe-network'),
      makeSnapshotRow(199, 'gas'),
    ]

    const rows = snapshotRowsToScoreRows(snapshotRows, buildTrackedProjectLookup(trackedProjects))

    expect(rows.map((row) => ({
      slug: row.slug,
      reportTypes: row.reportTypes,
      score: row.score,
    }))).toEqual([
      { slug: 'binancecoin', reportTypes: ['econ', 'maturity'], score: 83 },
      { slug: 'dai', reportTypes: ['econ', 'maturity'], score: 78 },
      { slug: 'the-open-network', reportTypes: ['econ', 'maturity'], score: 80 },
      { slug: 'usd1', reportTypes: ['econ', 'maturity'], score: 60 },
      { slug: 'hedera-hashgraph', reportTypes: ['econ', 'maturity'], score: 78 },
      { slug: 'pi-network', reportTypes: ['econ', 'maturity'], score: 70 },
      { slug: 'worldcoin', reportTypes: ['econ', 'maturity'], score: 72 },
      { slug: 'gate', reportTypes: ['econ', 'maturity'], score: 69 },
      { slug: 'flare-networks', reportTypes: ['econ', 'maturity'], score: 68 },
      { slug: 'maplestory-universe', reportTypes: ['econ', 'maturity'], score: 64 },
      { slug: 'awe-network', reportTypes: ['econ'], score: null },
      { slug: 'gas', reportTypes: ['econ', 'maturity'], score: 61 },
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
      maturityScore: null,
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
      maturityScore: null,
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
      maturityScore: null,
    })
  })

  it('falls back to MAT report card score when the tracked project score is empty', () => {
    const trackedProjects = [
      {
        id: 'river-project',
        name: 'River',
        slug: 'river',
        symbol: 'RIVER',
        category: 'Infrastructure',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: 'river',
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const availabilityByProjectSlug = buildReportAvailabilityByProjectSlug([
      {
        project_id: 'river-project',
        report_type: 'maturity',
        language: 'ko',
        published_at: '2026-05-30T12:03:10.455466+00:00',
        card_data: {
          maturity_score: 46,
        },
        slide_html_urls_by_lang: {
          ko: 'https://www.bcelab.xyz/reports/river/maturity',
        },
        tracked_projects: {
          slug: 'river',
        },
      },
    ], 'ko')

    const [row] = snapshotRowsToScoreRows(
      [
        {
          ...makeSnapshotRow(173, 'river-protocol'),
          cmc_name: 'River',
          cmc_symbol: 'RIVER',
        },
      ],
      buildTrackedProjectLookup(trackedProjects),
      undefined,
      availabilityByProjectSlug,
    )

    expect(row).toMatchObject({
      slug: 'river',
      score: 46,
      reportTypes: ['maturity'],
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
