import { render, screen } from '@testing-library/react'

import {
  cleanCardSummary,
  getLocaleReportState,
  getLocalizedSummary,
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

  it('renders without notFound when the requested locale row is missing but another language report exists', async () => {
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
          },
        },
      ],
    )

    const page = await SlideReportPage({ locale: 'ja', slug: 'usd-coin', reportType: 'econ' })
    render(page)

    expect(mockNotFound).not.toHaveBeenCalled()
    expect(screen.getByText('localePendingTitle')).toBeTruthy()
    expect(screen.getByText('localePendingDesc:JA')).toBeTruthy()
  })

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
    expect(screen.queryByText('english-only')).toBeNull()
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

  it('ignores empty and non-string locale entries', () => {
    expect(resolveSlideUrl({ ko: '', en: 'https://example.com/en.html' }, 'ko')).toBeNull()
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
