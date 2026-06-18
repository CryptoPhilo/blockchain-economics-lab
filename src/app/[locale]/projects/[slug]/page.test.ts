import { render, screen } from '@testing-library/react'

import ProjectDetailPage, {
  buildReportHref,
  selectProjectHeroBackground,
  selectReportsByType,
} from './page'
import type { ProjectReport } from '@/lib/types'

const mockCreateServerSupabaseClient = jest.fn()

jest.mock('@/lib/supabase-server', () => ({
  createServerSupabaseClient: () => mockCreateServerSupabaseClient(),
}))

jest.mock('next/navigation', () => ({
  notFound: jest.fn(() => {
    throw new Error('NEXT_NOT_FOUND')
  }),
}))

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

type MockQuery = {
  select: jest.Mock
  eq: jest.Mock
  in: jest.Mock
  order: jest.Mock
  single: jest.Mock
  then: <TResult1 = { data: unknown }, TResult2 = never>(
    onFulfilled?: ((value: { data: unknown }) => TResult1 | PromiseLike<TResult1>) | null | undefined,
    onRejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null | undefined,
  ) => Promise<TResult1 | TResult2>
}

function createQuery(data: unknown[] | unknown): MockQuery {
  const query: MockQuery = {
    select: jest.fn(() => query),
    eq: jest.fn(() => query),
    in: jest.fn(() => query),
    order: jest.fn(() => query),
    single: jest.fn(() => Promise.resolve({ data })),
    then: (resolve, reject) => Promise.resolve({ data }).then(resolve, reject),
  }

  return query
}

function mockProjectDetailQueries(project: unknown, reports: unknown[]) {
  const projectQuery = createQuery(project)
  const reportsQuery = createQuery(reports)

  mockCreateServerSupabaseClient.mockResolvedValue({
    from: jest.fn((table: string) => {
      if (table === 'tracked_projects') return projectQuery
      if (table === 'project_reports') return reportsQuery
      throw new Error(`Unexpected table: ${table}`)
    }),
  })

  return { projectQuery, reportsQuery }
}

beforeEach(() => {
  jest.clearAllMocks()
})

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

describe('project detail hero background', () => {
  it('selects the first report product cover as the project hero background', () => {
    const coverUrl = 'https://cdn.example.test/covers/tether-econ.png'
    const report = createReport({
      product: {
        id: 'product-tether-econ',
        type: 'single_report',
        status: 'published',
        slug: 'tether-econ',
        title_en: 'Tether ECON',
        price_usd_cents: 0,
        cover_image_url: coverUrl,
        tags: [],
        featured: false,
        created_at: '2026-04-24T00:00:00.000Z',
      },
    })

    expect(selectProjectHeroBackground([report], 'ko')).toBe(coverUrl)
  })

  it('renders a project detail header with the report cover as a background image', async () => {
    const coverUrl = 'https://cdn.example.test/covers/tether-econ.png'
    const { reportsQuery } = mockProjectDetailQueries(
      {
        id: 'tether',
        name: 'Tether',
        slug: 'tether',
        symbol: 'USDT',
        chain: 'Ethereum',
        category: 'stablecoin',
        status: 'active',
        discovered_at: '2026-04-01T00:00:00.000Z',
        market_cap_usd: 186_640_000_000,
        maturity_score: 48,
        maturity_stage: 'growing',
        forensic_monitoring: true,
        created_at: '2026-04-01T00:00:00.000Z',
      },
      [
        createReport({
          id: 'tether-econ-ko',
          project_id: 'tether',
          report_type: 'econ',
          title_ko: 'Tether ECON',
          product: {
            id: 'product-tether-econ',
            type: 'single_report',
            status: 'published',
            slug: 'tether-econ',
            title_en: 'Tether ECON',
            price_usd_cents: 0,
            cover_image_url: coverUrl,
            tags: [],
            featured: false,
            created_at: '2026-04-24T00:00:00.000Z',
          },
        }),
      ],
    )

    const page = await ProjectDetailPage({
      params: Promise.resolve({ locale: 'ko', slug: 'tether' }),
    })
    render(page)

    expect(reportsQuery.select).toHaveBeenCalledWith(
      '*, product:products(id, slug, title_en, title_ko, title_fr, title_es, title_de, title_ja, title_zh, cover_image_url, published_at)',
    )
    expect(screen.getByTestId('project-hero').getAttribute('style')).toContain(coverUrl)
    expect(screen.getByRole('heading', { level: 1, name: 'Tether' })).toBeTruthy()
  })
})
