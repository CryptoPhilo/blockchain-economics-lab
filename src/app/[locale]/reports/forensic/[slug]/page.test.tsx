import { render, screen } from '@testing-library/react'

import ForensicReportPage from './page'

const mockNotFound = jest.fn(() => {
  throw new Error('NEXT_NOT_FOUND')
})
const mockCreateServerSupabaseClient = jest.fn()

jest.mock('next/navigation', () => ({
  notFound: () => mockNotFound(),
}))

jest.mock('next-intl/server', () => ({
  getTranslations: jest.fn(async () => (key: string) => key),
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

jest.mock('@/components/GatedDownloadButton', () => ({
  __esModule: true,
  default: ({ label }: { label: string }) => {
    const React = jest.requireActual('react')
    return React.createElement('button', { type: 'button' }, label)
  },
}))

function createProjectQuery(project: unknown) {
  const query: Record<string, jest.Mock> = {}
  query.select = jest.fn(() => query)
  query.eq = jest.fn(() => query)
  query.single = jest.fn(async () => ({ data: project }))

  return query
}

function createReportsQuery(reports: unknown[]) {
  const query: Record<string, jest.Mock> = {}
  let orderCalls = 0

  query.select = jest.fn(() => query)
  query.eq = jest.fn(() => query)
  query.in = jest.fn(() => query)
  query.not = jest.fn(() => query)
  query.order = jest.fn(() => {
    orderCalls += 1
    return orderCalls >= 2 ? Promise.resolve({ data: reports }) : query
  })

  return query
}

function mockReportQueries(project: unknown, reports: unknown[]) {
  const projectQuery = createProjectQuery(project)
  const reportsQuery = createReportsQuery(reports)

  mockCreateServerSupabaseClient.mockResolvedValue({
    from: jest.fn((table: string) => {
      if (table === 'tracked_projects') return projectQuery
      if (table === 'project_reports') return reportsQuery
      throw new Error(`Unexpected table: ${table}`)
    }),
  })

  return { projectQuery, reportsQuery }
}

describe('ForensicReportPage slide deck rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders SlideViewer first when a forensic report has a locale slide URL', async () => {
    mockReportQueries({ id: 'project-1', slug: 'bitcoin', name: 'Bitcoin', symbol: 'BTC' }, [
      {
        id: 'report-en',
        language: 'en',
        report_type: 'forensic',
        status: 'published',
        version: 1,
        page_count: 12,
        card_risk_score: 72,
        risk_level: 'high',
        card_summary_en: 'Forensic summary.',
        card_data: {
          keywords_en: ['exchange outflow'],
          generated_at: '2026-05-01T00:00:00.000Z',
        },
        slide_html_urls_by_lang: {
          en: 'https://example.supabase.co/storage/v1/object/public/slides/forensic/bitcoin/latest/en.html',
        },
        gdrive_urls_by_lang: {
          en: 'https://drive.google.com/file/d/forensic-bitcoin/view',
        },
      },
    ])

    const page = await ForensicReportPage({
      params: Promise.resolve({ locale: 'en', slug: 'bitcoin' }),
    })

    render(page)

    expect(mockNotFound).not.toHaveBeenCalled()
    expect(screen.getByTestId('slide-viewer').getAttribute('data-url')).toBe(
      'https://example.supabase.co/storage/v1/object/public/slides/forensic/bitcoin/latest/en.html',
    )
    expect(screen.queryByText('Preview Snapshot')).toBeNull()
    expect(screen.queryByText('Report Access')).toBeNull()
    expect(screen.queryByRole('button', { name: /Get Free PDF/i })).toBeNull()
    expect(screen.getByRole('link', { name: /Open PDF report/i }).getAttribute('href')).toBe(
      'https://drive.google.com/file/d/forensic-bitcoin/view',
    )
  })

  it('renders an in-review forensic slide report on the canonical route', async () => {
    const { reportsQuery } = mockReportQueries(
      { id: 'project-2', slug: 'ethena', name: 'Ethena', symbol: 'ENA' },
      [
        {
          id: 'report-in-review-en',
          language: 'en',
          report_type: 'forensic',
          status: 'in_review',
          version: 1,
          page_count: 9,
          card_risk_score: 64,
          risk_level: 'elevated',
          card_summary_en: 'In review forensic summary.',
          card_data: {
            keywords_en: ['supply flow'],
            generated_at: '2026-05-10T00:00:00.000Z',
          },
          slide_html_urls_by_lang: {
            en: 'https://example.supabase.co/storage/v1/object/public/slides/forensic/ethena/latest/en.html',
          },
          gdrive_urls_by_lang: {
            en: 'https://drive.google.com/file/d/forensic-ethena/view',
          },
        },
      ],
    )

    const page = await ForensicReportPage({
      params: Promise.resolve({ locale: 'en', slug: 'ethena' }),
    })

    render(page)

    expect(mockNotFound).not.toHaveBeenCalled()
    expect(reportsQuery.in).toHaveBeenCalledWith('status', [
      'published',
      'coming_soon',
      'in_review',
    ])
    expect(reportsQuery.not).toHaveBeenCalledWith('slide_html_urls_by_lang', 'is', null)
    expect(screen.getByTestId('slide-viewer').getAttribute('data-url')).toBe(
      'https://example.supabase.co/storage/v1/object/public/slides/forensic/ethena/latest/en.html',
    )
    expect(screen.getByText('In review forensic summary.')).toBeTruthy()
  })
})
