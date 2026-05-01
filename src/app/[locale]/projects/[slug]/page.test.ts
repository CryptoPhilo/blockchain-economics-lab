import { selectReportsByType } from './page'
import type { ProjectReport } from '@/lib/types'

function createReport(overrides: Partial<ProjectReport> = {}): ProjectReport {
  return {
    id: 'report-btc-econ',
    project_id: 'bitcoin',
    report_type: 'econ',
    version: 1,
    status: 'published',
    language: 'ko',
    assigned_at: '2026-04-24T00:00:00.000Z',
    created_at: '2026-04-24T00:00:00.000Z',
    ...overrides,
  } as ProjectReport
}

describe('project detail report selection', () => {
  it('selects a Korean BTC ECON row for locales that have slide assets or English fallback', () => {
    const report = createReport({
      id: 'btc-econ-ko-row',
      language: 'ko',
      report_type: 'econ',
      slide_html_urls_by_lang: {
        en: 'https://example.com/en.html',
        ja: 'https://example.com/ja.html',
        ko: 'https://example.com/ko.html',
        zh: 'https://example.com/zh.html',
      },
      translation_status: {
        en: 'completed',
        ja: 'completed',
        ko: 'completed',
        zh: 'completed',
        de: 'published',
        es: 'published',
        fr: 'published',
      } as unknown as ProjectReport['translation_status'],
    } as Partial<ProjectReport>)

    expect(selectReportsByType([report], 'en').get('econ')).toBe(report)
    expect(selectReportsByType([report], 'ja').get('econ')).toBe(report)
    expect(selectReportsByType([report], 'zh').get('econ')).toBe(report)
    expect(selectReportsByType([report], 'de').get('econ')).toBe(report)
    expect(selectReportsByType([report], 'es').get('econ')).toBe(report)
    expect(selectReportsByType([report], 'fr').get('econ')).toBe(report)
  })
})
