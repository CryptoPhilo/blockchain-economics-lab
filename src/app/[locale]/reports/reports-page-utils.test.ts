import type { ProjectReport } from '@/lib/types'
import {
  buildMarketRankLookup,
  buildReportHistoryByProject,
  dedupeLatestReportsByProject,
  getMarketRankForReport,
  prepareRapidChangeReports,
} from './reports-page-utils'

function createReport(overrides: Partial<ProjectReport> & { project_id: string }): ProjectReport {
  const { project_id, ...rest } = overrides

  return {
    id: rest.id || `report-${project_id}`,
    project_id,
    report_type: 'forensic',
    version: 1,
    status: 'published',
    language: 'en',
    assigned_at: '2026-04-24T00:00:00.000Z',
    created_at: '2026-04-24T00:00:00.000Z',
    project: {
      id: project_id,
      name: project_id.toUpperCase(),
      slug: project_id,
      symbol: project_id.toUpperCase(),
      status: 'active',
      discovered_at: '2026-04-01T00:00:00.000Z',
      forensic_monitoring: true,
      created_at: '2026-04-01T00:00:00.000Z',
    },
    ...rest,
  } as ProjectReport
}

describe('rapid change report list helpers', () => {
  it('keeps only the latest report per project using published_at then created_at', () => {
    const reports = [
      createReport({
        id: 'alpha-old',
        project_id: 'alpha',
        status: 'coming_soon',
        created_at: '2026-04-24T10:00:00.000Z',
      }),
      createReport({
        id: 'alpha-new',
        project_id: 'alpha',
        status: 'published',
        created_at: '2026-04-24T11:00:00.000Z',
      }),
      createReport({
        id: 'beta-old',
        project_id: 'beta',
        status: 'published',
        published_at: '2026-04-24T08:00:00.000Z',
        created_at: '2026-04-24T07:00:00.000Z',
      }),
      createReport({
        id: 'beta-new',
        project_id: 'beta',
        status: 'coming_soon',
        published_at: '2026-04-24T08:00:00.000Z',
        created_at: '2026-04-24T09:30:00.000Z',
      }),
    ]

    const deduped = dedupeLatestReportsByProject(reports)

    expect(deduped).toHaveLength(2)
    expect(deduped.map((report) => report.id)).toEqual(['alpha-new', 'beta-old'])
  })

  it('deduplicates rapid-change placeholders and published reports for the same symbol', () => {
    const reports = [
      createReport({
        id: 'pol-placeholder',
        project_id: 'polygon-ecosystem-token',
        status: 'coming_soon',
        title_en: 'POL 11.0% Drop Detected: Forensic Analysis Initiated',
        created_at: '2026-06-05T10:17:38.000Z',
        project: {
          id: 'polygon-ecosystem-token',
          name: 'Polygon (prev. MATIC)',
          slug: 'polygon-ecosystem-token',
          symbol: 'POL',
          status: 'active',
          discovered_at: '2026-04-01T00:00:00.000Z',
          forensic_monitoring: true,
          created_at: '2026-04-01T00:00:00.000Z',
        },
      }),
      createReport({
        id: 'pol-published',
        project_id: 'pol-ex-matic',
        status: 'published',
        language: 'ko',
        title_ko: 'POL (ex-MATIC)',
        published_at: '2026-06-05T13:39:49.000Z',
        created_at: '2026-06-05T13:28:07.000Z',
        gdrive_urls_by_lang: { ko: { url: 'https://example.com/pol-ko.pdf' } },
        project: {
          id: 'pol-ex-matic',
          name: 'POL (ex-MATIC)',
          slug: 'pol-ex-matic',
          symbol: 'POL',
          coingecko_id: 'polygon-ecosystem-token',
          status: 'active',
          discovered_at: '2026-04-01T00:00:00.000Z',
          forensic_monitoring: true,
          created_at: '2026-04-01T00:00:00.000Z',
        },
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['pol-published'])
  })

  it('suppresses alias placeholders when a published forensic report exists for the same symbol', () => {
    const reports = [
      createReport({
        id: 'op-placeholder',
        project_id: 'optimism-ethereum',
        status: 'coming_soon',
        title_ko: 'OP 16.2% 하락 감지: 포렌식 분석 개시',
        is_latest: true,
        updated_at: '2026-06-06T09:00:00.000Z',
        created_at: '2026-06-06T09:00:00.000Z',
        project: {
          id: 'optimism-ethereum',
          name: 'Optimism',
          slug: 'optimism-ethereum',
          symbol: 'OP',
          status: 'monitoring_only',
          discovered_at: '2026-04-01T00:00:00.000Z',
          forensic_monitoring: true,
          created_at: '2026-04-01T00:00:00.000Z',
        },
      }),
      createReport({
        id: 'optimism-published',
        project_id: 'optimism',
        status: 'published',
        language: 'ko',
        title_ko: 'Optimism',
        is_latest: true,
        published_at: '2026-06-06T06:17:49.000Z',
        updated_at: '2026-06-06T06:17:51.000Z',
        created_at: '2026-06-06T06:17:49.000Z',
        slide_html_urls_by_lang: { ko: 'https://example.com/optimism-ko.html' },
        project: {
          id: 'optimism',
          name: 'Optimism',
          slug: 'optimism',
          symbol: 'OP',
          status: 'active',
          discovered_at: '2026-04-01T00:00:00.000Z',
          forensic_monitoring: true,
          created_at: '2026-04-01T00:00:00.000Z',
        },
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['optimism-published'])
  })

  it('filters, deduplicates, and paginates the rapid change list', () => {
    const reports = [
      createReport({
        id: 'alpha-old',
        project_id: 'alpha',
        title_en: 'Alpha risk update',
        created_at: '2026-04-24T10:00:00.000Z',
      }),
      createReport({
        id: 'alpha-new',
        project_id: 'alpha',
        title_en: 'Alpha risk update v2',
        status: 'published',
        created_at: '2026-04-24T11:00:00.000Z',
      }),
      createReport({
        id: 'beta',
        project_id: 'beta',
        title_en: 'Beta recovery report',
        created_at: '2026-04-24T09:00:00.000Z',
      }),
      createReport({
        id: 'gamma',
        project_id: 'gamma',
        title_en: 'Gamma market alert',
        created_at: '2026-04-24T12:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'en',
      page: 1,
      pageSize: 2,
      searchQuery: 'alpha',
    })

    expect(result.totalCount).toBe(1)
    expect(result.totalPages).toBe(1)
    expect(result.currentPage).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['alpha-new'])
  })

  it('prefers is_latest and keeps older project versions available for history links', () => {
    const oldReport = createReport({
      id: 'alpha-v1',
      project_id: 'alpha',
      version: 1,
      is_latest: false,
      created_at: '2026-04-24T12:00:00.000Z',
    })
    const latestReport = createReport({
      id: 'alpha-v2',
      project_id: 'alpha',
      version: 2,
      is_latest: true,
      created_at: '2026-04-24T10:00:00.000Z',
    })

    const latest = dedupeLatestReportsByProject([oldReport, latestReport])

    expect(latest).toEqual([latestReport])
    expect(buildReportHistoryByProject([oldReport, latestReport], latest).get('alpha')).toEqual([
      oldReport,
    ])
  })

  it('excludes same-version sibling language rows from report history', () => {
    const oldReport = createReport({
      id: 'alpha-v1-ko',
      project_id: 'alpha',
      version: 1,
      language: 'ko',
      is_latest: false,
      published_at: '2026-04-20T00:00:00.000Z',
      gdrive_urls_by_lang: { ko: { url: 'https://example.com/alpha-v1-ko.pdf' } },
    })
    const latestKo = createReport({
      id: 'alpha-v2-ko',
      project_id: 'alpha',
      version: 2,
      language: 'ko',
      is_latest: true,
      published_at: '2026-04-24T10:00:00.000Z',
      gdrive_urls_by_lang: { ko: { url: 'https://example.com/alpha-v2-ko.pdf' } },
    })
    const latestEnSibling = createReport({
      id: 'alpha-v2-en',
      project_id: 'alpha',
      version: 2,
      language: 'en',
      is_latest: true,
      published_at: '2026-04-24T10:00:00.000Z',
      gdrive_urls_by_lang: { en: { url: 'https://example.com/alpha-v2-en.pdf' } },
    })

    const history = buildReportHistoryByProject(
      [oldReport, latestKo, latestEnSibling],
      [latestKo],
    )

    expect(history.get('alpha')?.map((report) => report.id)).toEqual(['alpha-v1-ko'])
  })

  it('keeps the same latest report even when it lacks locale-specific assets', () => {
    const reports = [
      createReport({
        id: 'alpha-zh-new',
        project_id: 'alpha',
        language: 'zh',
        title_zh: 'Alpha 中文报告',
        created_at: '2026-04-24T12:00:00.000Z',
      }),
      createReport({
        id: 'alpha-ko-old',
        project_id: 'alpha',
        language: 'ko',
        title_ko: 'Alpha 한국어 보고서',
        gdrive_urls_by_lang: { ko: { url: 'https://example.com/ko.pdf' } },
        created_at: '2026-04-24T10:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['alpha-zh-new'])
  })

  it('keeps language-scoped forensic rows in every locale list', () => {
    const reports = [
      createReport({
        id: 'alpha-zh',
        project_id: 'alpha',
        language: 'zh',
        title_zh: 'Alpha 中文报告',
        card_summary_zh: '中文摘要',
        gdrive_urls_by_lang: { zh: { url: 'https://example.com/zh.pdf' } },
        created_at: '2026-04-24T12:00:00.000Z',
      }),
      createReport({
        id: 'beta-en-ko-asset',
        project_id: 'beta',
        language: 'en',
        title_ko: 'Beta 한국어 보고서',
        gdrive_urls_by_lang: { ko: { url: 'https://example.com/ko.pdf' } },
        translation_status: { ko: 'completed' } as ProjectReport['translation_status'],
        created_at: '2026-04-24T11:00:00.000Z',
      }),
      createReport({
        id: 'gamma-ko',
        project_id: 'gamma',
        language: 'ko',
        title_ko: 'Gamma 한국어 보고서',
        created_at: '2026-04-24T10:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(3)
    expect(result.reports.map((report) => report.id)).toEqual([
      'alpha-zh',
      'beta-en-ko-asset',
      'gamma-ko',
    ])
  })

  it('returns the same project list across locales', () => {
    const reports = [
      createReport({
        id: 'alpha-zh',
        project_id: 'alpha',
        language: 'zh',
        title_zh: 'Alpha 中文报告',
        created_at: '2026-04-24T12:00:00.000Z',
      }),
      createReport({
        id: 'beta-ko',
        project_id: 'beta',
        language: 'ko',
        title_ko: 'Beta 한국어 보고서',
        created_at: '2026-04-24T11:00:00.000Z',
      }),
      createReport({
        id: 'gamma-en',
        project_id: 'gamma',
        language: 'en',
        title_en: 'Gamma English report',
        created_at: '2026-04-24T10:00:00.000Z',
      }),
    ]

    const getIds = (locale: string) => prepareRapidChangeReports({
      reports,
      locale,
      page: 1,
      pageSize: 20,
    }).reports.map((report) => report.id)

    expect(getIds('ko')).toEqual(['alpha-zh', 'beta-ko', 'gamma-en'])
    expect(getIds('en')).toEqual(getIds('ko'))
    expect(getIds('ja')).toEqual(getIds('ko'))
  })

  it('does not require translation status for language-invariant lists', () => {
    const reports = [
      createReport({
        id: 'alpha-en-stale-ko-status',
        project_id: 'alpha',
        language: 'en',
        title_en: 'Alpha English report',
        translation_status: { ko: 'completed' } as ProjectReport['translation_status'],
        created_at: '2026-04-24T12:00:00.000Z',
      }),
      createReport({
        id: 'beta-ko',
        project_id: 'beta',
        language: 'ko',
        title_ko: 'Beta 한국어 보고서',
        created_at: '2026-04-24T11:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(2)
    expect(result.reports.map((report) => report.id)).toEqual([
      'alpha-en-stale-ko-status',
      'beta-ko',
    ])
  })

  it('includes coming soon forensic candidates without localized assets on Korean rapid change list', () => {
    const reports = [
      createReport({
        id: 'alpha-en-published-no-ko-asset',
        project_id: 'alpha',
        language: 'en',
        title_en: 'Alpha English report',
        status: 'published',
        created_at: '2026-04-24T12:00:00.000Z',
      }),
      createReport({
        id: 'beta-bce-1849-candidate',
        project_id: 'beta',
        language: 'en',
        title_en: 'Beta rapid change alert',
        title_ko: 'Beta 급변동 알림',
        status: 'coming_soon',
        trigger_reason: 'Exchange inflows crossed the rapid-change threshold.',
        created_at: '2026-04-24T11:00:00.000Z',
      }),
      createReport({
        id: 'gamma-market-candidate',
        project_id: 'gamma',
        language: 'en',
        title_en: 'Gamma market alert',
        title_ko: 'Gamma 시장 알림',
        status: 'coming_soon',
        report_type: 'market' as unknown as ProjectReport['report_type'],
        created_at: '2026-04-24T10:00:00.000Z',
      }),
      createReport({
        id: 'delta-ko-published',
        project_id: 'delta',
        language: 'ko',
        title_ko: 'Delta 한국어 보고서',
        status: 'published',
        created_at: '2026-04-24T09:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(3)
    expect(result.reports.map((report) => report.id)).toEqual([
      'alpha-en-published-no-ko-asset',
      'beta-bce-1849-candidate',
      'delta-ko-published',
    ])
  })

  it('does not depend on Korean asset markers for list membership', () => {
    const reports = [
      createReport({
        id: 'alpha-zh-empty-ko-markers',
        project_id: 'alpha',
        language: 'zh',
        title_zh: 'Alpha 中文报告',
        card_data: {
          summary_by_lang: { ko: '   ' },
          keywords_by_lang: { ko: [] },
        },
        gdrive_urls_by_lang: {
          ko: {},
          zh: { url: 'https://example.com/zh.pdf' },
        } as unknown as ProjectReport['gdrive_urls_by_lang'],
        file_urls_by_lang: { ko: '   ' } as ProjectReport['file_urls_by_lang'],
        created_at: '2026-04-24T12:00:00.000Z',
      }),
      createReport({
        id: 'beta-en-empty-ko-markers',
        project_id: 'beta',
        language: 'en',
        title_en: 'Beta English report',
        card_data: {
          keywords_by_lang: { ko: ['', '   '] },
        },
        gdrive_urls_by_lang: {
          ko: { download_url: '   ' },
          en: { url: 'https://example.com/en.pdf' },
        } as unknown as ProjectReport['gdrive_urls_by_lang'],
        created_at: '2026-04-24T11:00:00.000Z',
      }),
      createReport({
        id: 'gamma-ko',
        project_id: 'gamma',
        language: 'ko',
        title_ko: 'Gamma 한국어 보고서',
        gdrive_urls_by_lang: { ko: { url: 'https://example.com/ko.pdf' } },
        created_at: '2026-04-24T10:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(3)
    expect(result.reports.map((report) => report.id)).toEqual([
      'alpha-zh-empty-ko-markers',
      'beta-en-empty-ko-markers',
      'gamma-ko',
    ])
  })

  it('keeps Chinese reports on the English rapid change list with title fallback', () => {
    const reports = [
      createReport({
        id: 'alpha-zh-with-en-title',
        project_id: 'alpha',
        language: 'zh',
        title_en: 'Alpha English metadata title',
        title_zh: 'Alpha 中文报告',
        card_summary_en: 'English card metadata is not enough to expose the report.',
        created_at: '2026-04-24T12:00:00.000Z',
      }),
      createReport({
        id: 'beta-en',
        project_id: 'beta',
        language: 'en',
        title_en: 'Beta English report',
        created_at: '2026-04-24T11:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'en',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(2)
    expect(result.reports.map((report) => report.id)).toEqual([
      'alpha-zh-with-en-title',
      'beta-en',
    ])
  })

  it('includes an English row for a translated report on the English rapid change list', () => {
    const reports = [
      createReport({
        id: 'alpha-en-translated-row',
        project_id: 'alpha',
        language: 'en',
        title_en: 'Alpha English report',
        title_zh: 'Alpha 中文报告',
        gdrive_urls_by_lang: { en: { url: 'https://example.com/en.pdf' } },
        created_at: '2026-04-24T12:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'en',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['alpha-en-translated-row'])
  })

  it('keeps legacy language-less rows eligible when they have a localized asset', () => {
    const reports = [
      createReport({
        id: 'alpha-legacy-ko-asset',
        project_id: 'alpha',
        language: undefined,
        gdrive_urls_by_lang: { ko: { url: 'https://example.com/ko.pdf' } },
        created_at: '2026-04-24T12:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
    })

    expect(result.totalCount).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['alpha-legacy-ko-asset'])
  })

  it('filters rapid-change cards to projects that have a Top 500 CMC rank', () => {
    const reports = [
      createReport({
        id: 'ranked-redstone',
        project_id: 'redstone',
        title_en: 'RedStone rapid change',
        created_at: '2026-06-19T03:00:00.000Z',
        project: {
          id: 'redstone',
          name: 'RedStone',
          slug: 'redstone',
          symbol: 'RED',
          status: 'active',
          discovered_at: '2026-04-01T00:00:00.000Z',
          forensic_monitoring: true,
          created_at: '2026-04-01T00:00:00.000Z',
        },
      }),
      createReport({
        id: 'unranked-jpmx',
        project_id: 'jpmorgan-chase-tokenized-stock-xstock',
        title_en: 'JPMX rapid change',
        status: 'coming_soon',
        created_at: '2026-06-19T04:00:00.000Z',
        project: {
          id: 'jpmorgan-chase-tokenized-stock-xstock',
          name: 'JPMorgan Chase tokenized stock (xStock)',
          slug: 'jpmorgan-chase-tokenized-stock-xstock',
          symbol: 'JPMX',
          status: 'active',
          discovered_at: '2026-04-01T00:00:00.000Z',
          forensic_monitoring: true,
          created_at: '2026-04-01T00:00:00.000Z',
        },
      }),
    ]
    const marketRankLookup = buildMarketRankLookup([
      {
        slug: 'redstone',
        cmc_symbol: 'RED',
        cmc_name: 'RedStone',
        cmc_rank: 439,
        price_usd: null,
        market_cap: null,
        change_24h: null,
        recorded_at: '2026-06-19T00:00:00.000Z',
      },
    ])

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
      marketRankLookup,
    })

    expect(result.totalCount).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['ranked-redstone'])
  })

  it('fails closed when the rapid-change rank lookup cannot be loaded', () => {
    const reports = [
      createReport({
        id: 'alpha-ranked-only-with-snapshot',
        project_id: 'alpha',
        title_en: 'Alpha rapid change',
        created_at: '2026-06-19T03:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
      marketRankLookup: new Map(),
    })

    expect(result.totalCount).toBe(0)
    expect(result.reports).toEqual([])
  })

  it('filters rapid-change reports by published_at before falling back to created_at', () => {
    const reports = [
      createReport({
        id: 'old-published-rebackfilled',
        project_id: 'old-published-rebackfilled',
        published_at: '2026-06-10T00:00:00.000Z',
        created_at: '2026-06-20T00:00:00.000Z',
      }),
      createReport({
        id: 'recent-published',
        project_id: 'recent-published',
        published_at: '2026-06-20T00:00:00.000Z',
        created_at: '2026-06-01T00:00:00.000Z',
      }),
      createReport({
        id: 'recent-placeholder',
        project_id: 'recent-placeholder',
        status: 'coming_soon',
        published_at: undefined,
        created_at: '2026-06-20T00:00:00.000Z',
      }),
    ]

    const result = prepareRapidChangeReports({
      reports,
      locale: 'ko',
      page: 1,
      pageSize: 20,
      recencyCutoff: '2026-06-17T00:00:00.000Z',
    })

    expect(result.reports.map((report) => report.id)).toEqual([
      'recent-published',
      'recent-placeholder',
    ])
  })

  it('maps rapid-change cards to CMC ranks by project identity fields', () => {
    const report = createReport({
      id: 'undeads-forensic',
      project_id: 'undeads-games',
      project: {
        id: 'undeads-games',
        name: 'Undeads Games',
        slug: 'undeads-games',
        symbol: 'UDS',
        aliases: ['Undeads'],
        status: 'active',
        discovered_at: '2026-04-01T00:00:00.000Z',
        forensic_monitoring: true,
        created_at: '2026-04-01T00:00:00.000Z',
      },
    })
    const lookup = buildMarketRankLookup([
      {
        slug: 'undeads-games',
        cmc_symbol: 'UDS',
        cmc_name: 'Undeads Games',
        cmc_rank: 246,
        price_usd: null,
        market_cap: null,
        change_24h: null,
        recorded_at: '2026-06-14T00:00:00.000Z',
      },
    ])

    expect(getMarketRankForReport(report, lookup)).toBe(246)
  })

  it('ignores malformed and out-of-range market ranks', () => {
    const report = createReport({
      id: 'alpha-forensic',
      project_id: 'alpha',
      project: {
        id: 'alpha',
        name: 'Alpha',
        slug: 'alpha',
        symbol: 'ALPHA',
        status: 'active',
        discovered_at: '2026-04-01T00:00:00.000Z',
        forensic_monitoring: true,
        created_at: '2026-04-01T00:00:00.000Z',
      },
    })
    const lookup = buildMarketRankLookup([
      {
        slug: 'alpha',
        cmc_symbol: 'ALPHA',
        cmc_name: 'Alpha',
        cmc_rank: 501,
        price_usd: null,
        market_cap: null,
        change_24h: null,
        recorded_at: '2026-06-14T00:00:00.000Z',
      },
    ])

    expect(getMarketRankForReport(report, lookup)).toBeNull()
  })
})
