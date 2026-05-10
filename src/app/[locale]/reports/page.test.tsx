import { render, screen } from '@testing-library/react'

import ReportsPage from './page'

const mockCreateServerSupabaseClient = jest.fn()

jest.mock('next-intl/server', () => ({
  getTranslations: jest.fn(async () => (key: string) => key),
}))

jest.mock('@/lib/supabase-server', () => ({
  createServerSupabaseClient: () => mockCreateServerSupabaseClient(),
}))

type MockReportQuery = {
  select: jest.Mock
  in: jest.Mock
  eq: jest.Mock
  gte: jest.Mock
  order: jest.Mock
  then: <TResult1 = { data: unknown[] }, TResult2 = never>(
    onFulfilled?: ((value: { data: unknown[] }) => TResult1 | PromiseLike<TResult1>) | null | undefined,
    onRejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null | undefined,
  ) => Promise<TResult1 | TResult2>
}

function createReportsQuery(data: unknown[]) {
  const query: MockReportQuery = {
    select: jest.fn(() => query),
    in: jest.fn(() => query),
    eq: jest.fn(() => query),
    gte: jest.fn(() => query),
    order: jest.fn(() => query),
    then: (resolve, reject) => Promise.resolve({ data }).then(resolve, reject),
  }

  return query
}

function mockReportsQuery(data: unknown[]) {
  const reportsQuery = createReportsQuery(data)

  mockCreateServerSupabaseClient.mockResolvedValue({
    from: jest.fn((table: string) => {
      if (table !== 'project_reports') {
        throw new Error(`Unexpected table: ${table}`)
      }

      return reportsQuery
    }),
  })

  return reportsQuery
}

describe('ReportsPage rapid change cards', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders a Korean coming soon candidate without report assets as a non-link badge', async () => {
    const reportsQuery = mockReportsQuery([
      {
        id: 'bce-1849-candidate-ko',
        project_id: 'hyperliquid',
        report_type: 'forensic',
        version: 1,
        status: 'coming_soon',
        assigned_at: '2026-05-08T00:00:00.000Z',
        created_at: '2026-05-08T10:00:00.000Z',
        title_en: 'Hyperliquid rapid change alert',
        title_ko: 'Hyperliquid 급변동 알림',
        project: {
          id: 'hyperliquid',
          name: 'Hyperliquid',
          slug: 'hyperliquid',
          symbol: 'HYPE',
          chain: 'Hyperliquid',
          category: 'DEX',
        },
      },
    ])

    const page = await ReportsPage({
      params: Promise.resolve({ locale: 'ko' }),
      searchParams: Promise.resolve({}),
    })
    render(page)

    expect(reportsQuery.in).toHaveBeenCalledWith('status', ['published', 'coming_soon'])
    expect(reportsQuery.eq).toHaveBeenCalledWith('report_type', 'forensic')
    expect(reportsQuery.gte).toHaveBeenCalledWith('created_at', expect.any(String))
    expect(screen.getByText('실시간 업데이트 • 1건의 최신 보고서')).toBeTruthy()
    expect(screen.getByText('Hyperliquid 급변동 알림')).toBeTruthy()
    expect(screen.getByText('Hyperliquid (HYPE)')).toBeTruthy()
    expect(screen.getByText(/준비 중/).closest('a')).toBeNull()
  })
})
