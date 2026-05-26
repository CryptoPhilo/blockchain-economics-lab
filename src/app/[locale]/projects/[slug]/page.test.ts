import {
  buildReportHistoryByType,
  buildReportHref,
  getReportCoverImageUrls,
  pickProjectBackgroundCoverUrl,
  pickLocalizedTitle,
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
  it('derives card titles from the current project instead of stale report row titles', () => {
    const report = createReport({
      id: 'ethereum-mat-contaminated-title',
      report_type: 'maturity',
      language: 'ko',
      title_ko: 'lido MAT ko',
      card_summary_ko: 'Ethereum summary text',
    } as Partial<ProjectReport>)

    expect(pickLocalizedTitle(report, 'ko', 'Ethereum')).toBe('Ethereum')
  })

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

  it('falls back to the latest version that supports the requested locale', () => {
    const koV1 = createReport({
      id: 'eth-econ-v1-ko',
      project_id: 'ethereum',
      report_type: 'econ',
      language: 'ko',
      version: 1,
      is_latest: false,
      published_at: '2026-05-01T00:00:00.000Z',
      gdrive_urls_by_lang: { ko: 'https://drive.google.com/file/d/eth-econ-v1-ko/view' },
    } as Partial<ProjectReport>)
    const enV2 = createReport({
      id: 'eth-econ-v2-en',
      project_id: 'ethereum',
      report_type: 'econ',
      language: 'en',
      version: 2,
      is_latest: true,
      published_at: '2026-05-25T00:00:00.000Z',
      gdrive_urls_by_lang: { en: 'https://drive.google.com/file/d/eth-econ-v2-en/view' },
    } as Partial<ProjectReport>)

    const selected = selectReportsByType([koV1, enV2], 'ko')

    expect(selected.get('econ')).toBe(koV1)
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
})

describe('project detail cover backgrounds', () => {
  it('prefers locale cover, then English cover, then any available cover within the selected report version', () => {
    const report = createReport({
      cover_image_urls_by_lang: {
        en: 'https://example.com/en-cover.png',
        ko: 'https://example.com/ko-cover.png',
      },
    })

    expect(getReportCoverImageUrls(report, 'ko')).toEqual([
      'https://example.com/ko-cover.png',
      'https://example.com/en-cover.png',
    ])
    expect(getReportCoverImageUrls(report, 'ja')).toEqual([
      'https://example.com/en-cover.png',
      'https://example.com/ko-cover.png',
    ])
  })

  it('uses the latest report with a cover as the project background', () => {
    const older = createReport({
      id: 'older-report',
      published_at: '2026-05-01T00:00:00.000Z',
      cover_image_urls_by_lang: { ko: 'https://example.com/older-ko-cover.png' },
    })
    const newer = createReport({
      id: 'newer-report',
      published_at: '2026-05-20T00:00:00.000Z',
      cover_image_urls_by_lang: { ko: 'https://example.com/newer-ko-cover.png' },
    })
    const newestWithoutCover = createReport({
      id: 'newest-without-cover',
      published_at: '2026-05-25T00:00:00.000Z',
      cover_image_urls_by_lang: null,
    })

    expect(pickProjectBackgroundCoverUrl([older, newestWithoutCover, newer], 'ko')).toBe(
      'https://example.com/newer-ko-cover.png',
    )
  })

  it('keeps the project background on the newest report version instead of falling back to an older localized cover', () => {
    const olderKo = createReport({
      id: 'kaspa-econ-ko',
      language: 'ko',
      published_at: '2026-05-07T00:00:00.000Z',
      cover_image_urls_by_lang: { ko: 'https://example.com/kaspa-ko-cover.png' },
    })
    const newerZh = createReport({
      id: 'kaspa-econ-zh',
      language: 'zh',
      published_at: '2026-05-08T00:00:00.000Z',
      cover_image_urls_by_lang: {
        en: 'https://example.com/kaspa-en-cover.png',
        zh: 'https://example.com/kaspa-zh-cover.png',
      },
    })

    expect(pickProjectBackgroundCoverUrl([newerZh, olderKo], 'ko')).toBe(
      'https://example.com/kaspa-en-cover.png',
    )
    expect(pickProjectBackgroundCoverUrl([newerZh, olderKo], 'zh')).toBe(
      'https://example.com/kaspa-zh-cover.png',
    )
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
