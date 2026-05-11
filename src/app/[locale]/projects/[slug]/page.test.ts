import { buildReportHref, selectReportsByType } from './page'
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

  it('selects PDF-only legacy rows as project-page report cards', () => {
    const legacyPdfOnly = createReport({
      id: 'dexe-econ-legacy-pdf',
      language: 'en',
      report_type: 'econ',
      gdrive_urls_by_lang: {
        de: 'https://drive.google.com/file/d/dexe-de/view',
        en: 'https://drive.google.com/file/d/dexe-en/view',
        es: 'https://drive.google.com/file/d/dexe-es/view',
        fr: 'https://drive.google.com/file/d/dexe-fr/view',
        ja: 'https://drive.google.com/file/d/dexe-ja/view',
        ko: 'https://drive.google.com/file/d/dexe-ko/view',
        zh: 'https://drive.google.com/file/d/dexe-zh/view',
      },
      slide_html_urls_by_lang: null,
    } as Partial<ProjectReport>)

    expect(selectReportsByType([legacyPdfOnly], 'en').get('econ')).toBe(legacyPdfOnly)
    expect(selectReportsByType([legacyPdfOnly], 'ja').get('econ')).toBe(legacyPdfOnly)
    expect(selectReportsByType([legacyPdfOnly], 'de').get('econ')).toBe(legacyPdfOnly)
  })

  it('does not select rows that have no report asset for the requested locale', () => {
    const zhOnly = createReport({
      id: 'alpha-zh-only',
      language: 'zh',
      report_type: 'econ',
      gdrive_urls_by_lang: {
        zh: 'https://drive.google.com/file/d/alpha-zh/view',
      },
      slide_html_urls_by_lang: null,
    } as Partial<ProjectReport>)

    expect(selectReportsByType([zhOnly], 'ko').has('econ')).toBe(false)
    expect(selectReportsByType([zhOnly], 'en').has('econ')).toBe(false)
    expect(selectReportsByType([zhOnly], 'zh').get('econ')).toBe(zhOnly)
  })
})

describe('project detail report links', () => {
  it('uses the legacy slide route shape for ECON and MAT reports', () => {
    expect(buildReportHref('ko', 'bitcoin', 'econ')).toBe('/ko/reports/bitcoin/econ')
    expect(buildReportHref('ko', 'ethereum', 'maturity')).toBe('/ko/reports/ethereum/maturity')
  })

  it('uses the actual forensic detail route for FOR reports', () => {
    expect(buildReportHref('ko', 'aerodrome-finance', 'forensic')).toBe(
      '/ko/reports/forensic/aerodrome-finance',
    )
  })
})
