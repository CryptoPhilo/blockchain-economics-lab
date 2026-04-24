import type { ProjectReport } from '@/lib/types'
import { dedupeLatestReportsByProject, prepareRapidChangeReports } from './reports-page-utils'

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
      page: 1,
      pageSize: 2,
      searchQuery: 'alpha',
    })

    expect(result.totalCount).toBe(1)
    expect(result.totalPages).toBe(1)
    expect(result.currentPage).toBe(1)
    expect(result.reports.map((report) => report.id)).toEqual(['alpha-new'])
  })
})
