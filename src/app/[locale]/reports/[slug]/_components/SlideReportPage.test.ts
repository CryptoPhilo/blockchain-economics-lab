import { render, screen } from '@testing-library/react'

import {
  cleanCardSummary,
  getLocaleReportState,
  getLocalizedSummary,
  getReportDisplayDate,
  resolveReportPdfUrl,
  resolveSlideUrl,
} from './slide-report-utils'
import { SlideReportPage } from './SlideReportPage'

const mockNotFound = jest.fn(() => {
  throw new Error('NEXT_NOT_FOUND')
})
const mockCreateServerSupabaseClient = jest.fn()

jest.mock('next/navigation', () => ({
  notFound: () => mockNotFound(),
}))

jest.mock('next-intl/server', () => ({
  getTranslations: jest.fn(async () => (key: string, values?: Record<string, string>) => (
    values?.locale ? `${key}:${values.locale}` : key
  )),
}))

jest.mock('@/lib/supabase-server', () => ({
  createServerSupabaseClient: () => mockCreateServerSupabaseClient(),
}))

jest.mock('@/components/SlideViewer', () => ({
  __esModule: true,
  default: ({ htmlUrl }: { htmlUrl: string }) => {
    const React = jest.requireActual('react')
    return React.createElement('div', {
      'data-testid': 'slide-viewer',
      'data-url': htmlUrl,
    })
  },
}))

function createQuery(result: unknown, terminal: 'single' | 'order') {
  const query: Record<string, jest.Mock> = {}
  query.select = jest.fn(() => query)
  query.eq = jest.fn(() => query)
  query.in = jest.fn(() => query)
  query.single = jest.fn(async () => ({ data: terminal === 'single' ? result : null }))
  query.order = jest.fn(async () => ({ data: terminal === 'order' ? result : null }))

  return query
}

function mockReportQueries(project: unknown, reports: unknown[]) {
  const projectQuery = createQuery(project, 'single')
  const reportsQuery = createQuery(reports, 'order')

  mockCreateServerSupabaseClient.mockResolvedValue({
    from: jest.fn((table: string) => {
      if (table === 'tracked_projects') return projectQuery
      if (table === 'project_reports') return reportsQuery
      throw new Error(`Unexpected table: ${table}`)
    }),
  })
}

describe('SlideReportPage locale availability', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it.each(['de', 'es', 'fr'])(
    'renders the English fallback slide on the %s route when the requested locale asset is missing',
    async (locale) => {
      mockReportQueries(
        { id: 'project-1', slug: 'usd-coin', name: 'USD Coin', symbol: 'USDC' },
        [
          {
            id: 'report-en',
            language: 'en',
            report_type: 'econ',
            status: 'published',
            version: 1,
            card_data: {
              summary: 'English content must not be reused for Japanese.',
              keywords: ['english-only'],
              summary_en: 'English fallback summary.',
              keywords_en: ['English fallback keyword'],
            },
            slide_html_urls_by_lang: {
              en: 'https://example.test/en.html',
            },
          },
        ],
      )

      const page = await SlideReportPage({ locale, slug: 'usd-coin', reportType: 'econ' })
      render(page)

      expect(mockNotFound).not.toHaveBeenCalled()
      expect(screen.getByTestId('slide-viewer').getAttribute('data-url')).toBe(
        'https://example.test/en.html',
      )
      expect(screen.queryByText('English fallback summary.')).toBeNull()
      expect(screen.getByText('English fallback keyword')).toBeTruthy()
      expect(screen.getByText(locale)).toBeTruthy()
      expect(screen.queryByText('localePendingTitle')).toBeNull()
    },
  )

  it('renders a sibling-row slide URL without exposing English summary on the requested locale route', async () => {
    mockReportQueries(
      { id: 'project-1', slug: 'usd-coin', name: 'USD Coin', symbol: 'USDC' },
      [
        {
          id: 'report-en',
          language: 'en',
          report_type: 'econ',
          status: 'published',
          version: 1,
          card_data: {
            summary: 'English content must not be reused for Japanese.',
            keywords: ['english-only'],
          },
          slide_html_urls_by_lang: {
            en: 'https://example.test/en.html',
            ja: 'https://example.supabase.co/storage/v1/object/public/slides/econ/usd-coin/latest/ja.html',
          },
        },
      ],
    )

    const page = await SlideReportPage({ locale: 'ja', slug: 'usd-coin', reportType: 'econ' })

    render(page)

    expect(mockNotFound).not.toHaveBeenCalled()
    expect(screen.getByTestId('slide-viewer').getAttribute('data-url')).toBe(
      'https://example.supabase.co/storage/v1/object/public/slides/econ/usd-coin/latest/ja.html',
    )
    expect(screen.queryByText('English content must not be reused for Japanese.')).toBeNull()
    expect(screen.getByText('english-only')).toBeTruthy()
  })

  it('renders localized marketing content separately from the card summary', async () => {
    mockReportQueries(
      { id: 'project-1', slug: 'bitcoin', name: 'Bitcoin', symbol: 'BTC' },
      [
        {
          id: 'report-ko',
          language: 'ko',
          report_type: 'econ',
          status: 'published',
          version: 1,
          card_summary_ko: '요약 문장',
          marketing_content_by_lang: {
            ko: '장기 투자 관점 문장',
            en: 'English investment view',
          },
          slide_html_urls_by_lang: {
            ko: 'https://example.test/ko.html',
          },
        },
      ],
    )

    const page = await SlideReportPage({ locale: 'ko', slug: 'bitcoin', reportType: 'econ' })
    render(page)

    expect(screen.getByText('요약 문장')).toBeTruthy()
    expect(screen.getByText('투자 관점')).toBeTruthy()
    expect(screen.getByText('장기 투자 관점 문장')).toBeTruthy()
  })

  it('renders forensic slide reports through the shared report viewer', async () => {
    mockReportQueries(
      { id: 'project-1', slug: 'hedera-hashgraph', name: 'Hedera', symbol: 'HBAR' },
      [
        {
          id: 'report-ko',
          language: 'ko',
          report_type: 'forensic',
          status: 'published',
          version: 1,
          card_risk_score: 58,
          card_summary_ko: '포렌식 리스크 요약',
          slide_html_urls_by_lang: {
            ko: 'https://example.test/for/hedera/ko.html',
          },
        },
      ],
    )

    const page = await SlideReportPage({
      locale: 'ko',
      slug: 'hedera-hashgraph',
      reportType: 'forensic',
    })
    render(page)

    expect(mockNotFound).not.toHaveBeenCalled()
    expect(screen.getByTestId('slide-viewer').getAttribute('data-url')).toBe(
      'https://example.test/for/hedera/ko.html',
    )
    expect(screen.getByText('forensicLabel')).toBeTruthy()
    expect(screen.getByText('scoreLabel 58')).toBeTruthy()
    expect(screen.getByText('포렌식 리스크 요약')).toBeTruthy()
  })

  it('uses the latest locale-available version on default report routes', async () => {
    mockReportQueries(
      { id: 'project-1', slug: 'monero', name: 'Monero', symbol: 'XMR' },
      [
        {
          id: 'report-en-v2',
          language: 'en',
          report_type: 'forensic',
          status: 'published',
          version: 2,
          card_risk_score: 61,
          card_summary_en: 'English v2 forensic summary.',
          card_data: {
            generated_at: '2026-06-01T04:05:52.000Z',
            keywords_en: ['English v2 signal'],
          },
          slide_html_urls_by_lang: {
            en: 'https://example.test/for/monero/v2/en.html',
          },
        },
        {
          id: 'report-ko-v1',
          language: 'ko',
          report_type: 'forensic',
          status: 'published',
          version: 1,
          card_risk_score: 61,
          card_summary_ko: '한국어 v1 포렌식 요약',
          card_data: {
            generated_at: '2026-06-01T03:45:31.000Z',
            keywords_ko: ['한국어 v1 신호'],
          },
          slide_html_urls_by_lang: {
            ko: 'https://example.test/for/monero/v1/ko.html',
          },
        },
      ],
    )

    const page = await SlideReportPage({
      locale: 'ko',
      slug: 'monero',
      reportType: 'forensic',
    })
    render(page)

    expect(mockNotFound).not.toHaveBeenCalled()
    expect(screen.getByTestId('slide-viewer').getAttribute('data-url')).toBe(
      'https://example.test/for/monero/v1/ko.html',
    )
    expect(screen.queryByText('localePendingTitle')).toBeNull()
    expect(screen.getByText('한국어 v1 포렌식 요약')).toBeTruthy()
    expect(screen.queryByText('English v2 forensic summary.')).toBeNull()
  })

  it('renders slide-coming-soon instead of locale-pending when the English Google Drive PDF exists without a slide URL', async () => {
    mockReportQueries(
      { id: 'project-1', slug: 'litecoin', name: 'Litecoin', symbol: 'LTC' },
      [
        {
          id: 'report-litecoin-ko',
          language: 'ko',
          report_type: 'econ',
          status: 'published',
          version: 1,
          card_data: {
            summary_en: 'Litecoin English PDF summary.',
            keywords_en: ['Litecoin PDF'],
          },
          gdrive_urls_by_lang: {
            en: { url: 'https://drive.google.com/file/d/litecoin-en/view' },
          },
        },
      ],
    )

    const page = await SlideReportPage({ locale: 'en', slug: 'litecoin', reportType: 'econ' })
    render(page)

    expect(mockNotFound).not.toHaveBeenCalled()
    expect(screen.queryByTestId('slide-viewer')).toBeNull()
    expect(screen.queryByText('slideComingSoonTitle')).toBeNull()
    expect(screen.queryByText('slideComingSoonDesc')).toBeNull()
    expect(screen.getByRole('link', { name: /Open PDF Report/ }).getAttribute('href')).toBe(
      'https://drive.google.com/file/d/litecoin-en/view',
    )
    expect(screen.queryByText('localePendingTitle')).toBeNull()
    expect(screen.queryByText('localePendingDesc:EN')).toBeNull()
    expect(screen.getByText('Litecoin English PDF summary.')).toBeTruthy()
  })

  it('renders the Ethena English PDF CTA when the English report has no slide URL', async () => {
    mockReportQueries(
      { id: 'ethena', slug: 'ethena', name: 'Ethena', symbol: 'ENA' },
      [
        {
          id: 'ethena-en',
          language: 'en',
          report_type: 'econ',
          status: 'published',
          version: 1,
          gdrive_urls_by_lang: {
            en: 'https://drive.google.com/file/d/1EFts9d07kjs2-Q24cexj9oLoVkzHE27E/view',
            ko: 'https://drive.google.com/file/d/1Cvd6n0yFVFk4clDi4AO2zJ2KNXPpDA3d/view',
          },
          slide_html_urls_by_lang: {
            ja: 'https://example.supabase.co/storage/v1/object/public/slides/econ/ethena/latest/ja.html',
            ko: 'https://example.supabase.co/storage/v1/object/public/slides/econ/ethena/latest/ko.html',
            zh: 'https://example.supabase.co/storage/v1/object/public/slides/econ/ethena/latest/zh.html',
          },
        },
      ],
    )

    const page = await SlideReportPage({ locale: 'en', slug: 'ethena', reportType: 'econ' })
    render(page)

    expect(mockNotFound).not.toHaveBeenCalled()
    expect(screen.queryByTestId('slide-viewer')).toBeNull()
    expect(screen.getByRole('link', { name: /Open PDF Report/ }).getAttribute('href')).toBe(
      'https://drive.google.com/file/d/1EFts9d07kjs2-Q24cexj9oLoVkzHE27E/view',
    )
    expect(screen.queryByText('localePendingTitle')).toBeNull()
  })

  it('keeps the project-missing path as notFound', async () => {
    mockReportQueries(null, [])

    await expect(
      SlideReportPage({ locale: 'ja', slug: 'missing-project', reportType: 'econ' }),
    ).rejects.toThrow('NEXT_NOT_FOUND')
    expect(mockNotFound).toHaveBeenCalledTimes(1)
  })
})

describe('getLocalizedSummary', () => {
  it('uses DB summary metadata in the documented locale priority order', () => {
    const report = {
      language: 'ko',
      card_summary_ko: 'row column summary',
    }
    const cardData = {
      summary_by_lang: { ko: 'summary by lang' },
      summary_ko: 'card data locale summary',
      summary: 'generic same-locale summary',
    }

    expect(getLocalizedSummary('ko', report, cardData)).toBe('summary by lang')
    expect(getLocalizedSummary('ko', report, { ...cardData, summary_by_lang: {} })).toBe(
      'row column summary',
    )
    expect(getLocalizedSummary('ko', { language: 'ko' }, { ...cardData, summary_by_lang: {} })).toBe(
      'card data locale summary',
    )
    expect(getLocalizedSummary('ko', { language: 'ko' }, { summary: 'generic same-locale summary' })).toBe(
      'generic same-locale summary',
    )
  })

  it('falls back to English summary metadata only on English routes', () => {
    const report = {
      language: 'en',
      card_summary_en: 'English row summary',
    }
    const cardData = {
      summary_en: 'English card data summary',
      summary: 'Generic English source summary',
    }

    expect(getLocalizedSummary('ja', report, cardData)).toBe('')
    expect(getLocalizedSummary('en', report, cardData)).toBe('English row summary')
  })

  it('uses Japanese summary metadata without falling through to English fields', () => {
    expect(
      getLocalizedSummary(
        'ja',
        { language: 'en', card_summary_en: 'English row summary' },
        {
          summary_by_lang: { ja: '日本語の要約' },
          summary_ja: 'カードデータの日本語要約',
          summary_en: 'English card data summary',
        },
      ),
    ).toBe('日本語の要約')

    expect(
      getLocalizedSummary(
        'ja',
        {
          language: 'en',
          card_summary_en: 'English row summary',
          card_summary_ja: '行の日本語要約',
        },
        {
          summary_by_lang: {},
          summary_ja: 'カードデータの日本語要約',
          summary_en: 'English card data summary',
        },
      ),
    ).toBe('行の日本語要約')

    expect(
      getLocalizedSummary(
        'ja',
        { language: 'en', card_summary_en: 'English row summary' },
        {
          summary_by_lang: {},
          summary_ja: 'カードデータの日本語要約',
          summary_en: 'English card data summary',
        },
      ),
    ).toBe('カードデータの日本語要約')
  })
})

describe('resolveSlideUrl', () => {
  it('returns the exact locale slide URL', () => {
    expect(resolveSlideUrl({ ko: 'https://example.com/ko.html' }, 'ko')).toBe(
      'https://example.com/ko.html',
    )
  })

  it('does not fall back from Korean to another slide language', () => {
    expect(
      resolveSlideUrl(
        {
          en: 'https://example.com/en.html',
          zh: 'https://example.com/zh.html',
        },
        'ko',
      ),
    ).toBeNull()
  })

  it.each(['de', 'es', 'fr'])('falls back from %s to the canonical English slide', (locale) => {
    expect(
      resolveSlideUrl(
        {
          en: 'https://example.com/en.html',
          zh: 'https://example.com/zh.html',
        },
        locale,
      ),
    ).toBe('https://example.com/en.html')
  })

  it('ignores empty and non-string locale entries', () => {
    expect(resolveSlideUrl({ de: '', en: 'https://example.com/en.html' }, 'de')).toBe(
      'https://example.com/en.html',
    )
    expect(resolveSlideUrl({ ko: { url: 'https://example.com/ko.html' } }, 'ko')).toBeNull()
  })

  it('rejects a locale key whose storage URL points at another language artifact', () => {
    expect(
      resolveSlideUrl(
        {
          ja: 'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/zh.html',
        },
        'ja',
      ),
    ).toBeNull()
  })

  it('accepts matching locale artifacts in the storage path', () => {
    expect(
      resolveSlideUrl(
        {
          ja: 'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/ja.html',
        },
        'ja',
      ),
    ).toBe(
      'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/ja.html',
    )
  })
})

describe('resolveReportPdfUrl', () => {
  it('returns the exact locale Google Drive URL', () => {
    expect(
      resolveReportPdfUrl(
        {
          language: 'en',
          gdrive_urls_by_lang: {
            en: 'https://drive.google.com/file/d/ethena-en/view',
            ko: 'https://drive.google.com/file/d/ethena-ko/view',
          },
        },
        'en',
      ),
    ).toBe('https://drive.google.com/file/d/ethena-en/view')
  })

  it.each(['de', 'es', 'fr'])('falls back from %s to English PDF assets', (locale) => {
    expect(
      resolveReportPdfUrl(
        {
          language: 'ko',
          gdrive_urls_by_lang: {
            en: { download_url: 'https://drive.google.com/uc?id=ethena-en&export=download' },
          },
        },
        locale,
        true,
      ),
    ).toBe('https://drive.google.com/uc?id=ethena-en&export=download')
  })

  it('does not fall back from Japanese to English PDF assets', () => {
    expect(
      resolveReportPdfUrl(
        {
          language: 'en',
          gdrive_urls_by_lang: {
            en: 'https://drive.google.com/file/d/ethena-en/view',
          },
        },
        'ja',
      ),
    ).toBeNull()
  })
})

describe('getReportDisplayDate', () => {
  it('uses the newest policy timestamp across sibling rows instead of a stale selected row date', () => {
    expect(
      getReportDisplayDate(
        [
          {
            id: 'avalanche-ko',
            published_at: '2026-04-16T12:29:22.000Z',
            created_at: '2026-04-13T11:32:40.000Z',
          },
          {
            id: 'avalanche-en',
            card_data: { generated_at: '2026-05-02T09:06:00.000Z' },
            published_at: '2026-04-16T12:29:22.000Z',
          },
        ],
        {
          id: 'avalanche-ko',
          published_at: '2026-04-16T12:29:22.000Z',
          created_at: '2026-04-13T11:32:40.000Z',
        },
      ),
    ).toBe('2026-05-02T09:06:00.000Z')
  })
})

describe('getLocaleReportState', () => {
  it('returns locale_pending when other language reports exist but the requested locale row is missing', () => {
    expect(
      getLocaleReportState(
        [
          { id: 'report-en', language: 'en' },
          { id: 'report-ko', language: 'ko' },
        ],
        'ja',
      ),
    ).toEqual({ status: 'locale_pending' })
  })

  it('returns an available sibling report when it carries an exact locale slide URL', () => {
    const report = {
      id: 'report-en',
      language: 'en',
      slide_html_urls_by_lang: {
        ja: 'https://example.supabase.co/storage/v1/object/public/slides/econ/usd-coin/latest/ja.html',
      },
    }

    expect(
      getLocaleReportState([report], 'ja'),
    ).toEqual({ status: 'available', report })
  })

  it.each(['de', 'es', 'fr'])(
    'returns an available sibling report for %s when only the English slide URL exists',
    (locale) => {
      const report = {
        id: 'report-btc',
        language: 'ko',
        slide_html_urls_by_lang: {
          en: 'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/en.html',
          ja: 'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/ja.html',
          ko: 'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/ko.html',
          zh: 'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/zh.html',
        },
      }

      expect(
        getLocaleReportState([report], locale),
      ).toEqual({ status: 'available', report })
    },
  )

  it('returns an available sibling report when the requested locale only has a Google Drive PDF', () => {
    const report = {
      id: 'report-litecoin-ko',
      language: 'ko',
      gdrive_urls_by_lang: {
        en: { url: 'https://drive.google.com/file/d/litecoin-en/view' },
      },
    }

    expect(
      getLocaleReportState([report], 'en'),
    ).toEqual({ status: 'available', report })
  })

  it('prefers slide HTML rows over PDF-only legacy rows for sibling locale availability', () => {
    const pdfOnlyReport = {
      id: 'report-legacy-pdf',
      language: 'ko',
      gdrive_urls_by_lang: {
        en: { url: 'https://drive.google.com/file/d/legacy-en/view' },
      },
    }
    const slideReport = {
      id: 'report-slide',
      language: 'ko',
      slide_html_urls_by_lang: {
        en: 'https://example.supabase.co/storage/v1/object/public/slides/econ/dexe/latest/en.html',
      },
    }

    expect(
      getLocaleReportState([pdfOnlyReport, slideReport], 'en'),
    ).toEqual({ status: 'available', report: slideReport })
  })

  it.each(['de', 'es', 'fr'])(
    'returns an available sibling report for %s when only the English Google Drive PDF exists',
    (locale) => {
      const report = {
        id: 'report-litecoin-ko',
        language: 'ko',
        gdrive_urls_by_lang: {
          en: { download_url: 'https://drive.google.com/uc?id=litecoin-en&export=download' },
        },
      }

      expect(
        getLocaleReportState([report], locale),
      ).toEqual({ status: 'available', report })
    },
  )

  it('does not treat a mismatched sibling slide URL as available', () => {
    expect(
      getLocaleReportState(
        [
          {
            id: 'report-en',
            language: 'en',
            slide_html_urls_by_lang: {
              ja: 'https://example.supabase.co/storage/v1/object/public/slides/econ/usd-coin/latest/zh.html',
            },
          },
        ],
        'ja',
      ),
    ).toEqual({ status: 'locale_pending' })
  })

  it('returns not_found when the project has no reports for the requested type', () => {
    expect(getLocaleReportState([], 'ja')).toEqual({ status: 'not_found' })
    expect(getLocaleReportState(null, 'ja')).toEqual({ status: 'not_found' })
  })

  it('returns the exact locale report when available', () => {
    const report = { id: 'report-ja', language: 'ja' }

    expect(
      getLocaleReportState(
        [
          { id: 'report-en', language: 'en' },
          report,
        ],
        'ja',
      ),
    ).toEqual({ status: 'available', report })
  })
})

describe('cleanCardSummary', () => {
  it('returns empty string for null/undefined/non-string', () => {
    expect(cleanCardSummary(null)).toBe('')
    expect(cleanCardSummary(undefined)).toBe('')
    expect(cleanCardSummary('')).toBe('')
  })

  it('drops markdown headings that leaked from the source report', () => {
    const raw =
      '솔라나 네트워크의 경제 시스템을 구성하는 핵심 개념들은 온체인 상태(state)와 긴밀하게 연결되어 있다. ### 1.1 프로젝트 기본 정보 | 항목 | 상세 내용 |'
    expect(cleanCardSummary(raw)).toBe(
      '솔라나 네트워크의 경제 시스템을 구성하는 핵심 개념들은 온체인 상태(state)와 긴밀하게 연결되어 있다.',
    )
  })

  it('drops inline table markup', () => {
    const raw =
      "Summarizing key indicators. | Metrics | 2024 | 2025 | | :---- | :---- | :---- |"
    expect(cleanCardSummary(raw)).toBe('Summarizing key indicators.')
  })

  it('strips bold and link markdown', () => {
    expect(cleanCardSummary('See **the docs** at [link](https://x.test) for more.'))
      .toBe('See the docs at link for more.')
  })

  it('removes inline citation markers like [1]', () => {
    expect(cleanCardSummary('First fact [1]. Second fact [12].'))
      .toBe('First fact. Second fact.')
  })

  it('collapses whitespace and trims', () => {
    expect(cleanCardSummary('  A   B\n\nC  ')).toBe('A B C')
  })

  it('passes through clean prose unchanged in meaning', () => {
    const clean = '솔라나는 고성능 PoH 합의 기반의 레이어1 블록체인이다.'
    expect(cleanCardSummary(clean)).toBe(clean)
  })

  it('cuts at the first list bullet rather than retaining structural list', () => {
    expect(cleanCardSummary('Overview. - bullet one - bullet two')).toBe('Overview.')
  })
})
