import { pickLocaleReport, reportSupportsLocale } from './report-locale'
import type { ProjectReport } from './types'

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

describe('report locale helpers', () => {
  it('treats locale asset maps as support even when the row language differs', () => {
    const report = createReport({
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

    expect(reportSupportsLocale(report, 'en')).toBe(true)
    expect(reportSupportsLocale(report, 'ja')).toBe(true)
    expect(reportSupportsLocale(report, 'zh')).toBe(true)
    expect(reportSupportsLocale(report, 'ko')).toBe(true)
    expect(reportSupportsLocale(report, 'de')).toBe(true)
    expect(reportSupportsLocale(report, 'es')).toBe(true)
    expect(reportSupportsLocale(report, 'fr')).toBe(true)
  })

  it('keeps language-scoped rows restricted to their exact language without locale assets', () => {
    const report = createReport({
      language: 'ko',
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

    expect(reportSupportsLocale(report, 'ko')).toBe(true)
    expect(reportSupportsLocale(report, 'en')).toBe(false)
    expect(reportSupportsLocale(report, 'de')).toBe(false)
  })

  it('selects a sibling row with a locale asset when no exact locale row exists', () => {
    const report = createReport({
      id: 'btc-econ-ko-row',
      language: 'ko',
      slide_html_urls_by_lang: {
        en: 'https://example.com/en.html',
        ja: 'https://example.com/ja.html',
        ko: 'https://example.com/ko.html',
        zh: 'https://example.com/zh.html',
      },
    })

    expect(pickLocaleReport([report], 'en')).toBe(report)
    expect(pickLocaleReport([report], 'ja')).toBe(report)
    expect(pickLocaleReport([report], 'zh')).toBe(report)
    expect(pickLocaleReport([report], 'de')).toBe(report)
    expect(pickLocaleReport([report], 'es')).toBe(report)
    expect(pickLocaleReport([report], 'fr')).toBe(report)
  })

  it('still prefers exact locale rows over asset-bearing sibling rows', () => {
    const sharedAssetRow = createReport({
      id: 'btc-econ-ko-shared-assets',
      language: 'ko',
      slide_html_urls_by_lang: {
        en: 'https://example.com/en.html',
      },
    })
    const exactRow = createReport({
      id: 'btc-econ-en-row',
      language: 'en',
    })

    expect(pickLocaleReport([sharedAssetRow, exactRow], 'en')).toBe(exactRow)
  })

  it('prefers a locale asset row over an English fallback asset row', () => {
    const englishFallbackRow = createReport({
      id: 'btc-econ-ko-en-assets',
      language: 'ko',
      slide_html_urls_by_lang: {
        en: 'https://example.com/en.html',
      },
    })
    const localeAssetRow = createReport({
      id: 'btc-econ-shared-de-assets',
      language: 'fr',
      slide_html_urls_by_lang: {
        de: 'https://example.com/de.html',
      },
    })

    expect(pickLocaleReport([englishFallbackRow, localeAssetRow], 'de')).toBe(localeAssetRow)
  })
})
