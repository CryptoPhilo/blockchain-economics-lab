import {
  buildReportAvailabilityByProjectId,
  fetchVisibleReportsForProjectIds,
  type VisibleReportRow,
} from './report-availability'

function makeReport(overrides: Partial<VisibleReportRow> = {}): VisibleReportRow {
  return {
    project_id: 'project-1',
    report_type: 'forensic',
    status: 'published',
    language: 'ko',
    published_at: '2026-06-19T00:00:00.000Z',
    gdrive_urls_by_lang: {
      ko: { url: 'https://drive.google.com/file/d/report-ko/view' },
    },
    ...overrides,
  }
}

describe('report availability helpers', () => {
  it('does not count coming-soon report rows as exchange or scoreboard badges', () => {
    const availability = buildReportAvailabilityByProjectId([
      makeReport({
        status: 'coming_soon',
        published_at: null,
      }),
    ], 'ko')

    expect(availability.has('project-1')).toBe(false)
  })

  it('keeps published and review-ready localized rows available', () => {
    const availability = buildReportAvailabilityByProjectId([
      makeReport({
        project_id: 'published-project',
        report_type: 'econ',
        status: 'published',
      }),
      makeReport({
        project_id: 'review-project',
        report_type: 'maturity',
        status: 'in_review',
        updated_at: '2026-06-20T00:00:00.000Z',
      }),
    ], 'ko')

    expect(availability.get('published-project')?.reportTypes).toEqual(['econ'])
    expect(availability.get('review-project')?.reportTypes).toEqual(['maturity'])
  })

  it('queries only statuses that project detail pages can render', async () => {
    const inCalls: Array<{ column: string; values: readonly unknown[] }> = []
    const query = {
      select: jest.fn(),
      in: jest.fn(),
      range: jest.fn(),
    }
    query.select.mockReturnValue(query)
    query.in.mockImplementation((column: string, values: readonly unknown[]) => {
      inCalls.push({ column, values })
      return query
    })
    query.range.mockResolvedValue({ data: [], error: null })
    const supabase = {
      from: jest.fn(() => query),
    }

    const result = await fetchVisibleReportsForProjectIds(
      ['project-1'],
      supabase as never,
    )

    expect(result.loaded).toBe(true)
    expect(supabase.from).toHaveBeenCalledWith('project_reports')
    expect(query.select).toHaveBeenCalledWith(expect.stringContaining('status'))
    expect(inCalls).toContainEqual({
      column: 'status',
      values: ['published', 'in_review'],
    })
  })
})
