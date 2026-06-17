import {
  buildReportAvailabilityByProjectId,
  buildTrackedProjectLookup,
  canonicalSnapshotRowsToScoreRows,
  fetchVisibleReportsForScoreboard,
  getCanonicalSnapshotReportProjectIds,
  hasCompleteCmcCanonicalTop500Snapshot,
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

  it('preserves CMC rank on score rows for the project-name badge', () => {
    const [row] = snapshotRowsToScoreRows(
      [makeSnapshotRow(298, 'usd-ai')],
      buildTrackedProjectLookup([]),
    )

    expect(row).toMatchObject({
      rank: 298,
      cmcRank: 298,
      slug: 'usd-ai',
    })
  })

  it('limits report availability lookups to projects matched by the canonical Top 500 snapshot', () => {
    const trackedProjects = Array.from({ length: 650 }, (_, index) => {
      const rank = index + 1
      return {
        id: `project-${rank}`,
        name: `Project ${rank}`,
        slug: `cmc-project-${rank}`,
        symbol: `P${rank}`,
        category: 'L1',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      }
    })
    const snapshotRows = Array.from({ length: 500 }, (_, index) => makeSnapshotRow(index + 1))

    const ids = getCanonicalSnapshotReportProjectIds(snapshotRows, trackedProjects)

    expect(ids).toHaveLength(500)
    expect(ids).toContain('project-1')
    expect(ids).toContain('project-500')
    expect(ids).not.toContain('project-501')
    expect(ids).not.toContain('project-650')
  })

  it('keeps report availability alias sources when the Top 500 row is an alias target', () => {
    const trackedProjects = [
      {
        id: 'falcon-usd-project',
        name: 'Falcon USD',
        slug: 'falcon-usd',
        symbol: 'USDf',
        category: 'Stablecoins',
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
        id: 'falcon-finance-ff-project',
        name: 'Falcon Finance FF',
        slug: 'falcon-finance-ff',
        symbol: 'FF',
        category: 'Stablecoins',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: null,
        aliases: [],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [
      makeSnapshotRow(1, 'falcon-usd'),
      ...Array.from({ length: 499 }, (_, index) => makeSnapshotRow(index + 2)),
    ]

    const ids = getCanonicalSnapshotReportProjectIds(snapshotRows, trackedProjects)

    expect(ids).toEqual(['falcon-usd-project', 'falcon-finance-ff-project'])
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
    ]
    const snapshotRows = [
      makeSnapshotRow(89, 'sei-network'),
      makeSnapshotRow(90, 'pancakeswap-token'),
      makeSnapshotRow(95, 'injective-protocol'),
      makeSnapshotRow(100, 'curve-dao-token'),
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
    ])
  })

  it('keeps Circle EURC and EUR CoinVertible as separate CMC rows', () => {
    const trackedProjects = [
      {
        id: 'eurc-project',
        name: 'EURC',
        slug: 'eurc',
        symbol: 'EURC',
        category: 'Stablecoins',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: 'euro-coin',
        aliases: ['euro-coin'],
        maturity_score: 74,
        last_econ_report_at: '2026-06-01T16:26:14.739924Z',
        last_maturity_report_at: '2026-06-09T06:56:35.867095Z',
        last_forensic_report_at: null,
      },
      {
        id: 'eurcv-project',
        name: 'EUR CoinVertible',
        slug: 'eur-coinvertible',
        symbol: 'EURCV',
        category: 'Stablecoins',
        market_cap_usd: 50,
        coingecko_id: null,
        cmc_id: 'eur-coinvertible',
        aliases: ['EUR CoinVertible', 'EURCV', 'euro-coinvertible'],
        maturity_score: null,
        last_econ_report_at: null,
        last_maturity_report_at: null,
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [
      makeSnapshotRow(85, 'euro-coin'),
      makeSnapshotRow(238, 'eur-coinvertible'),
    ]

    const rows = snapshotRowsToScoreRows(snapshotRows, buildTrackedProjectLookup(trackedProjects))

    expect(rows.map((row) => ({
      rank: row.rank,
      name: row.name,
      slug: row.slug,
      symbol: row.symbol,
      reportTypes: row.reportTypes,
    }))).toEqual([
      {
        rank: 85,
        name: 'EURC',
        slug: 'eurc',
        symbol: 'EURC',
        reportTypes: ['econ', 'maturity'],
      },
      {
        rank: 238,
        name: 'EUR CoinVertible',
        slug: 'eur-coinvertible',
        symbol: 'EURCV',
        reportTypes: [],
      },
    ])
  })

  it('maps EUR CoinVertible to EURCV even before a tracked project row exists', () => {
    const trackedProjects = [
      {
        id: 'eurc-project',
        name: 'EURC',
        slug: 'eurc',
        symbol: 'EURC',
        category: 'Stablecoins',
        market_cap_usd: 100,
        coingecko_id: null,
        cmc_id: 'euro-coin',
        aliases: ['euro-coin'],
        maturity_score: 74,
        last_econ_report_at: '2026-06-01T16:26:14.739924Z',
        last_maturity_report_at: '2026-06-09T06:56:35.867095Z',
        last_forensic_report_at: null,
      },
    ]
    const snapshotRows = [makeSnapshotRow(238, 'eur-coinvertible')]

    const [row] = snapshotRowsToScoreRows(snapshotRows, buildTrackedProjectLookup(trackedProjects))

    expect(row).toMatchObject({
      rank: 238,
      name: 'EUR CoinVertible',
      slug: 'eur-coinvertible',
      symbol: 'EURCV',
      reportTypes: [],
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
      range: jest.fn().mockReturnThis(),
      then: undefined,
    }
    query.in
      .mockReturnValueOnce(query)
      .mockReturnValueOnce(query)
      .mockReturnValueOnce(query)
    query.range
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
    expect(query.range).toHaveBeenCalledWith(0, 999)
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

  it('does not fall back to an older localized version when the latest version lacks locale support', () => {
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

    expect(availability.has('alpha-project')).toBe(false)
  })

  it('uses a localized row from the latest version when another locale has a newer timestamp', () => {
    const availability = buildReportAvailabilityByProjectId([
      {
        id: 'stellar-econ-v2-en',
        project_id: 'stellar-project',
        report_type: 'econ',
        version: 2,
        is_latest: true,
        language: 'en',
        published_at: '2026-06-11T03:02:41.726383Z',
        updated_at: '2026-06-11T03:17:04.503990Z',
        gdrive_urls_by_lang: {
          en: { url: 'https://drive.google.com/file/d/stellar-v2-en/view' },
        },
      },
      {
        id: 'stellar-econ-v2-ko',
        project_id: 'stellar-project',
        report_type: 'econ',
        version: 2,
        is_latest: true,
        language: 'ko',
        published_at: '2026-06-11T03:02:41.726383Z',
        updated_at: '2026-06-11T03:11:08.415344Z',
        gdrive_urls_by_lang: {
          ko: { url: 'https://drive.google.com/file/d/stellar-v2-ko/view' },
        },
      },
    ], 'ko')

    expect(availability.get('stellar-project')).toEqual({
      reportTypes: ['econ'],
      reportDates: {
        econ: '2026-06-11T03:02:41.726383Z',
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
