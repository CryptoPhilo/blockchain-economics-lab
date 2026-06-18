import { buildReportAvailabilityByProjectId } from './report-availability'

describe('buildReportAvailabilityByProjectId', () => {
  it('does not expose a locale report badge when only a PDF/Drive URL exists', () => {
    const availability = buildReportAvailabilityByProjectId([
      {
        id: 'horizen-mat-ko-pdf-only',
        project_id: 'horizen-project',
        report_type: 'maturity',
        version: 1,
        language: 'ko',
        published_at: '2026-05-30T17:53:37.104983+00:00',
        gdrive_urls_by_lang: {
          ko: 'https://drive.google.com/file/d/horizen-ko/view',
        },
        slide_html_urls_by_lang: {},
      },
      {
        id: 'horizen-mat-ja-slide',
        project_id: 'horizen-project',
        report_type: 'maturity',
        version: 1,
        language: 'ja',
        published_at: '2026-05-30T18:54:51.211586+00:00',
        slide_html_urls_by_lang: {
          ja: 'https://www.bcelab.xyz/slides/mat/horizen/latest/ja.html',
        },
      },
    ], 'ko')

    expect(availability.get('horizen-project')).toBeUndefined()
  })

  it('falls back to an older localized slide version when the global latest version is another language', () => {
    const availability = buildReportAvailabilityByProjectId([
      {
        id: 'bitcoin-mat-v3-en',
        project_id: 'bitcoin-project',
        report_type: 'maturity',
        version: 3,
        language: 'en',
        published_at: '2026-06-17T08:42:17.463762+00:00',
        slide_html_urls_by_lang: {
          en: 'https://www.bcelab.xyz/slides/mat/bitcoin/latest/en.html',
        },
      },
      {
        id: 'bitcoin-mat-v2-ko',
        project_id: 'bitcoin-project',
        report_type: 'maturity',
        version: 2,
        language: 'ko',
        published_at: '2026-06-17T08:43:27.074239+00:00',
        slide_html_urls_by_lang: {
          ko: 'https://www.bcelab.xyz/slides/mat/bitcoin/latest/ko.html',
        },
      },
    ], 'ko')

    expect(availability.get('bitcoin-project')).toEqual({
      reportTypes: ['maturity'],
      reportDates: {
        econ: null,
        maturity: '2026-06-17T08:43:27.074239+00:00',
        forensic: null,
      },
    })
  })
})
