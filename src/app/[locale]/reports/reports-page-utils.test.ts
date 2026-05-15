import type { ProjectReport } from '@/lib/types'
import {
  buildReportHistoryByProject,
  dedupeLatestReportsByProject,
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

  it('does not fall back to an older localized report when the latest version lacks locale support', () => {
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

    expect(result.totalCount).toBe(0)
    expect(result.reports).toEqual([])
  })

  it('includes language-scoped rows in another locale when that locale has a real asset', () => {
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

    expect(result.totalCount).toBe(2)
    expect(result.reports.map((report) => report.id)).toEqual(['beta-en-ko-asset', 'gamma-ko'])
  })

  it('does not include language-scoped rows in another locale from translation status alone', () => {
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

    expect(result.totalCount).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['beta-ko'])
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

    expect(result.totalCount).toBe(2)
    expect(result.reports.map((report) => report.id)).toEqual([
      'beta-bce-1849-candidate',
      'delta-ko-published',
    ])
  })

  it('does not treat empty Korean card arrays or empty URL entries as Korean availability', () => {
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

    expect(result.totalCount).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['gamma-ko'])
  })

  it('excludes Chinese reports from the English rapid change list when only English title metadata exists', () => {
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

    expect(result.totalCount).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['beta-en'])
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
})
