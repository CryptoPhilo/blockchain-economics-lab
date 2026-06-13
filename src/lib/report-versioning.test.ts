import { compareReportVersions, pickLatestReport, sortReportsLatestFirst } from './report-versioning'

describe('report-versioning comparator', () => {
  it('prioritizes version number over is_latest when selecting latest report', () => {
    const oldLatestInLocale = {
      id: 'old-v1',
      project_id: 'bitcoin',
      report_type: 'maturity' as const,
      version: 1,
      is_latest: true,
      published_at: '2026-05-01T00:00:00.000Z',
    }
    const newNotLatest = {
      id: 'new-v2',
      project_id: 'bitcoin',
      report_type: 'maturity' as const,
      version: 2,
      is_latest: false,
      published_at: '2026-05-02T00:00:00.000Z',
    }

    expect(pickLatestReport([oldLatestInLocale, newNotLatest])).toEqual(newNotLatest)
    expect(sortReportsLatestFirst([oldLatestInLocale, newNotLatest])[0]).toEqual(newNotLatest)
  })

  it('uses is_latest as tie-breaker within the same version', () => {
    const olderLatestFlag = {
      id: 'v3-ko',
      project_id: 'bitcoin',
      report_type: 'maturity' as const,
      version: 3,
      is_latest: true,
    }
    const sameVersion = {
      id: 'v3-en',
      project_id: 'bitcoin',
      report_type: 'maturity' as const,
      version: 3,
      is_latest: false,
    }

    expect(compareReportVersions(olderLatestFlag, sameVersion)).toBeGreaterThan(0)
    expect(sortReportsLatestFirst([olderLatestFlag, sameVersion])[0]).toEqual(olderLatestFlag)
  })
})
