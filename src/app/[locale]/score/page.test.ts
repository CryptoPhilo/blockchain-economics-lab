import {
  buildTrackedProjectLookup,
  canonicalSnapshotRowsToScoreRows,
  hasCompleteCmcCanonicalTop200Snapshot,
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
