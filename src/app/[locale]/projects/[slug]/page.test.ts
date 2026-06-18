import {
  buildReportHistoryByType,
  buildReportHref,
  getProjectDetailHeaderStyle,
  selectReportsByType,
} from './page'
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

  it('selects the latest localized version and exposes older versions as history', () => {
    const oldReport = createReport({
      id: 'btc-econ-v1',
      version: 1,
      is_latest: false,
      language: 'ko',
      report_type: 'econ',
      published_at: '2026-05-01T00:00:00.000Z',
      gdrive_urls_by_lang: { ko: 'https://drive.google.com/file/d/btc-v1-ko/view' },
    } as Partial<ProjectReport>)
    const latestReport = createReport({
      id: 'btc-econ-v2',
      version: 2,
      is_latest: true,
      language: 'ko',
      report_type: 'econ',
      published_at: '2026-05-10T00:00:00.000Z',
      gdrive_urls_by_lang: { ko: 'https://drive.google.com/file/d/btc-v2-ko/view' },
    } as Partial<ProjectReport>)

    const selected = selectReportsByType([oldReport, latestReport], 'ko')

    expect(selected.get('econ')).toBe(latestReport)
    expect(buildReportHistoryByType([oldReport, latestReport], selected, 'ko').get('econ')).toEqual([
      oldReport,
    ])
  })

  it('does not expose same-version alternate language rows as history', () => {
    const oldReport = createReport({
      id: 'btc-econ-v1-ko',
      version: 1,
      is_latest: false,
      language: 'ko',
      report_type: 'econ',
      published_at: '2026-05-01T00:00:00.000Z',
      gdrive_urls_by_lang: { ko: 'https://drive.google.com/file/d/btc-v1-ko/view' },
    } as Partial<ProjectReport>)
    const latestKo = createReport({
      id: 'btc-econ-v2-ko',
      version: 2,
      is_latest: true,
      language: 'ko',
      report_type: 'econ',
      published_at: '2026-05-10T00:00:00.000Z',
      gdrive_urls_by_lang: { ko: 'https://drive.google.com/file/d/btc-v2-ko/view' },
    } as Partial<ProjectReport>)
    const latestEnSibling = createReport({
      id: 'btc-econ-v2-en',
      version: 2,
      is_latest: true,
      language: 'en',
      report_type: 'econ',
      published_at: '2026-05-10T00:00:00.000Z',
      gdrive_urls_by_lang: { en: 'https://drive.google.com/file/d/btc-v2-en/view' },
    } as Partial<ProjectReport>)

    const selected = selectReportsByType([oldReport, latestKo, latestEnSibling], 'ko')

    expect(selected.get('econ')).toBe(latestKo)
    expect(
      buildReportHistoryByType([oldReport, latestKo, latestEnSibling], selected, 'ko')
        .get('econ')
        ?.map((report) => report.id),
    ).toEqual(['btc-econ-v1-ko'])
  })

  it('chooses the newest version even if it is not marked as latest', () => {
    const oldVersion = createReport({
      id: 'btc-mat-v1-old',
      version: 1,
      is_latest: true,
      language: 'en',
      report_type: 'maturity',
      gdrive_urls_by_lang: { en: 'https://drive.google.com/file/d/btc-mat-v1-en/view' },
    } as Partial<ProjectReport>)
    const newVersion = createReport({
      id: 'btc-mat-v2-new',
      version: 2,
      is_latest: false,
      language: 'en',
      report_type: 'maturity',
      gdrive_urls_by_lang: { en: 'https://drive.google.com/file/d/btc-mat-v2-en/view' },
    } as Partial<ProjectReport>)

    const selected = selectReportsByType([oldVersion, newVersion], 'en')

    expect(selected.get('maturity')).toBe(newVersion)
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

describe('project detail header art', () => {
  it('uses the linked product cover image when present', () => {
    const reportWithCover = createReport({
      product: {
        id: 'product-usdai-econ',
        slug: 'usdai-econ',
        title_en: 'USDai ECON',
        cover_image_url: 'https://cdn.example.com/usdai-cover.jpg',
        published_at: '2026-06-08T00:00:00.000Z',
        type: 'single_report',
        status: 'published',
        price_usd_cents: 0,
        tags: [],
        featured: false,
        created_at: '2026-06-08T00:00:00.000Z',
      },
    } as unknown as Partial<ProjectReport>)

    const style = getProjectDetailHeaderStyle([reportWithCover], 'ko')

    expect(style.backgroundImage).toContain('https://cdn.example.com/usdai-cover.jpg')
  })

  it('falls back to a slide thumbnail when there is no linked product cover', () => {
    const reportWithSlide = createReport({
      slide_html_urls_by_lang: {
        ko: 'https://wbqponoiyoeqlepxogcb.supabase.co/storage/v1/object/public/slides/econ/usdai/latest/ko.html',
      },
    } as Partial<ProjectReport>)

    const style = getProjectDetailHeaderStyle([reportWithSlide], 'ko')

    expect(style.backgroundImage).toContain('/slides/econ/usdai/latest/ko-cover.jpg')
  })

  it('falls back to the shared project hero background when no cover assets exist', () => {
    const style = getProjectDetailHeaderStyle([], 'ko')

    expect(style.backgroundImage).toContain('/images/score-header-bg.png')
  })
})
