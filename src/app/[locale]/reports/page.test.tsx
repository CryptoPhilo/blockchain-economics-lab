import { render, screen } from '@testing-library/react'

import ReportsPage, { dynamic, revalidate } from './page'

const mockCreateServerSupabaseClient = jest.fn()
const mockGetLatestScoreboardMarketSnapshot = jest.fn()

jest.mock('next-intl/server', () => ({
  getTranslations: jest.fn(async () => (key: string) => key),
}))

jest.mock('@/lib/supabase-server', () => ({
  createServerSupabaseClient: () => mockCreateServerSupabaseClient(),
}))

jest.mock('@/lib/repositories/projects', () => ({
  createProjectsRepository: () => ({
    getLatestScoreboardMarketSnapshot: mockGetLatestScoreboardMarketSnapshot,
  }),
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
    mockGetLatestScoreboardMarketSnapshot.mockResolvedValue([])
  })

  it('forces dynamic rendering so locale pages cannot cache divergent rapid-change lists', () => {
    expect(dynamic).toBe('force-dynamic')
    expect(revalidate).toBe(0)
  })

  it('queries forensic reports from the last 72 hours and renders candidate card contract fields', async () => {
    const reportsQuery = mockReportsQuery([
      {
        id: 'eth-candidate',
        project_id: 'ethereum',
        report_type: 'forensic',
        version: 1,
        status: 'coming_soon',
        language: 'en',
        assigned_at: '2026-05-08T00:00:00.000Z',
        created_at: '2026-05-08T10:00:00.000Z',
        trigger_reason: 'Exchange inflows and whale transfers crossed the alert threshold.',
        project: {
          id: 'ethereum',
          name: 'Ethereum',
          slug: 'ethereum',
          symbol: 'ETH',
          chain: 'Ethereum',
          category: 'L1',
        },
      },
      {
        id: 'bitcoin-published',
        project_id: 'bitcoin',
        report_type: 'forensic',
        version: 2,
        status: 'published',
        language: 'en',
        assigned_at: '2026-05-08T00:00:00.000Z',
        created_at: '2026-05-08T09:00:00.000Z',
        published_at: '2026-05-08T11:00:00.000Z',
        card_data: {
          summary_by_lang: {
            en: 'Localized summary is used when trigger_reason is not present.',
          },
        },
        project: {
          id: 'bitcoin',
          name: 'Bitcoin',
          slug: 'bitcoin',
          symbol: 'BTC',
          chain: 'Bitcoin',
          category: 'L1',
        },
      },
    ])

    const page = await ReportsPage({
      params: Promise.resolve({ locale: 'en' }),
      searchParams: Promise.resolve({}),
    })
    render(page)

    expect(reportsQuery.in).toHaveBeenCalledWith('status', ['published', 'coming_soon', 'in_review'])
    expect(reportsQuery.eq).toHaveBeenCalledWith('report_type', 'forensic')
    expect(reportsQuery.gte).toHaveBeenCalledWith('created_at', expect.any(String))

    const gteIso = reportsQuery.gte.mock.calls[0][1] as string
    expect(Number.isNaN(Date.parse(gteIso))).toBe(false)

    expect(screen.getByText('Ethereum Forensic Analysis v1')).toBeTruthy()
    expect(screen.getByText('Ethereum (ETH)')).toBeTruthy()
    expect(screen.getByText(/Coming Soon/).closest('a')?.getAttribute('href')).toBe(
      '/en/reports/forensic/ethereum',
    )
    expect(screen.getByText('Exchange inflows and whale transfers crossed the alert threshold.')).toBeTruthy()

    expect(screen.getByText('Bitcoin Forensic Analysis v2')).toBeTruthy()
    expect(screen.getByText('Localized summary is used when trigger_reason is not present.')).toBeTruthy()
    expect(screen.getByRole('link', { name: /Report Details/ }).getAttribute('href')).toBe(
      '/en/reports/forensic/bitcoin',
    )
  })

  it('uses localized summary fallback for coming soon candidate reasons', async () => {
    mockReportsQuery([
      {
        id: 'sol-candidate-ko',
        project_id: 'solana',
        report_type: 'forensic',
        version: 1,
        status: 'coming_soon',
        language: 'en',
        assigned_at: '2026-05-08T00:00:00.000Z',
        created_at: '2026-05-08T10:00:00.000Z',
        card_data: {
          summary_by_lang: {
            ko: '거래소 유입과 파생 포지션 급증이 동시에 감지되었습니다.',
          },
        },
        gdrive_urls_by_lang: {
          ko: { url: 'https://example.test/solana-ko.pdf' },
        },
        project: {
          id: 'solana',
          name: 'Solana',
          slug: 'solana',
          symbol: 'SOL',
          chain: 'Solana',
          category: 'L1',
        },
      },
    ])

    const page = await ReportsPage({
      params: Promise.resolve({ locale: 'ko' }),
      searchParams: Promise.resolve({}),
    })
    render(page)

    expect(screen.getByText('감지 이유')).toBeTruthy()
    expect(screen.getByText('거래소 유입과 파생 포지션 급증이 동시에 감지되었습니다.')).toBeTruthy()
    expect(screen.getByText(/준비 중/).closest('a')?.getAttribute('href')).toBe(
      '/ko/reports/forensic/solana',
    )
  })

  it('renders a Korean coming soon candidate without report assets', async () => {
    mockReportsQuery([
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
        trigger_reason: '대규모 고래 이체와 거래소 유입이 동시에 감지되었습니다.',
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

    expect(screen.getByText('Hyperliquid 급변동 알림')).toBeTruthy()
    expect(screen.getByText('Hyperliquid (HYPE)')).toBeTruthy()
    expect(screen.getByText('대규모 고래 이체와 거래소 유입이 동시에 감지되었습니다.')).toBeTruthy()
    expect(screen.getByText(/준비 중/).closest('a')?.getAttribute('href')).toBe(
      '/ko/reports/forensic/hyperliquid',
    )
  })

  it('shows the CMC rank next to rapid-change project names', async () => {
    mockGetLatestScoreboardMarketSnapshot.mockResolvedValue([
      {
        slug: 'undeads-games',
        cmc_symbol: 'UDS',
        cmc_name: 'Undeads Games',
        cmc_rank: 246,
        price_usd: null,
        market_cap: null,
        change_24h: null,
        recorded_at: '2026-06-14T00:00:00.000Z',
      },
    ])
    mockReportsQuery([
      {
        id: 'undeads-published',
        project_id: 'undeads-games',
        report_type: 'forensic',
        version: 1,
        status: 'published',
        language: 'ko',
        assigned_at: '2026-06-14T00:00:00.000Z',
        created_at: '2026-06-14T10:00:00.000Z',
        title_ko: 'Undeads Games 포렌식 분석',
        trigger_reason: '시장 급변동이 감지되었습니다.',
        project: {
          id: 'undeads-games',
          name: 'Undeads Games',
          slug: 'undeads-games',
          symbol: 'UDS',
          chain: 'BNB Chain',
          category: 'GameFi',
          aliases: ['Undeads'],
        },
      },
    ])

    const page = await ReportsPage({
      params: Promise.resolve({ locale: 'ko' }),
      searchParams: Promise.resolve({}),
    })
    render(page)

    expect(screen.getByText('Undeads Games (UDS)')).toBeTruthy()
    expect(screen.getByText('#246')).toBeTruthy()
  })

  it('renders previous version links without same-version language siblings', async () => {
    mockReportsQuery([
      {
        id: 'alpha-v2-ko',
        project_id: 'alpha',
        report_type: 'forensic',
        version: 2,
        is_latest: true,
        status: 'published',
        language: 'ko',
        assigned_at: '2026-05-08T00:00:00.000Z',
        created_at: '2026-05-08T12:00:00.000Z',
        published_at: '2026-05-08T12:00:00.000Z',
        title_ko: 'Alpha 포렌식 분석 v2',
        gdrive_urls_by_lang: {
          ko: { url: 'https://example.test/alpha-v2-ko.pdf' },
        },
        project: {
          id: 'alpha',
          name: 'Alpha',
          slug: 'alpha',
          symbol: 'ALPHA',
          chain: 'Ethereum',
          category: 'DeFi',
        },
      },
      {
        id: 'alpha-v2-en',
        project_id: 'alpha',
        report_type: 'forensic',
        version: 2,
        is_latest: true,
        status: 'published',
        language: 'en',
        assigned_at: '2026-05-08T00:00:00.000Z',
        created_at: '2026-05-08T11:00:00.000Z',
        published_at: '2026-05-08T11:00:00.000Z',
        title_en: 'Alpha Forensic Analysis v2',
        gdrive_urls_by_lang: {
          en: { url: 'https://example.test/alpha-v2-en.pdf' },
        },
        project: {
          id: 'alpha',
          name: 'Alpha',
          slug: 'alpha',
          symbol: 'ALPHA',
          chain: 'Ethereum',
          category: 'DeFi',
        },
      },
      {
        id: 'alpha-v1-ko',
        project_id: 'alpha',
        report_type: 'forensic',
        version: 1,
        is_latest: false,
        status: 'published',
        language: 'ko',
        assigned_at: '2026-05-08T00:00:00.000Z',
        created_at: '2026-05-08T10:00:00.000Z',
        published_at: '2026-05-08T10:00:00.000Z',
        title_ko: 'Alpha 포렌식 분석 v1',
        gdrive_urls_by_lang: {
          ko: { url: 'https://example.test/alpha-v1-ko.pdf' },
        },
        project: {
          id: 'alpha',
          name: 'Alpha',
          slug: 'alpha',
          symbol: 'ALPHA',
          chain: 'Ethereum',
          category: 'DeFi',
        },
      },
    ])

    const page = await ReportsPage({
      params: Promise.resolve({ locale: 'ko' }),
      searchParams: Promise.resolve({}),
    })
    render(page)

    expect(screen.getByText('이전 버전')).toBeTruthy()
    expect(screen.getByRole('link', { name: /v1 · KO · FORENSIC/ }).getAttribute('href')).toBe(
      '/ko/reports/forensic/alpha?version=1&lang=ko&type=forensic',
    )
    expect(screen.queryByRole('link', { name: /v2 · EN · FORENSIC/ })).toBeNull()
  })
})
