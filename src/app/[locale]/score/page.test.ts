import {
  buildTrackedProjectLookup,
  hasCompleteCmcCanonicalTop200Snapshot,
  MIN_CMC_CANONICAL_TOP_200_SNAPSHOT_ROWS,
  snapshotRowsToScoreRows,
} from './page'

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
  it('rejects partial snapshots so score falls back to tracked projects', () => {
    expect(hasCompleteCmcCanonicalTop200Snapshot(1)).toBe(false)
    expect(hasCompleteCmcCanonicalTop200Snapshot(199)).toBe(false)
  })

  it('accepts only snapshots with at least 200 rows as canonical Top 200 data', () => {
    expect(hasCompleteCmcCanonicalTop200Snapshot(MIN_CMC_CANONICAL_TOP_200_SNAPSHOT_ROWS)).toBe(true)
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
})
