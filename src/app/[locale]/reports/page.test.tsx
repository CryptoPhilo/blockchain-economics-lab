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
  or: jest.Mock
  gte: jest.Mock
  lte: jest.Mock
  order: jest.Mock
  limit: jest.Mock
  maybeSingle: jest.Mock
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
    or: jest.fn(() => query),
    gte: jest.fn(() => query),
    lte: jest.fn(() => query),
    order: jest.fn(() => query),
    limit: jest.fn(() => query),
    maybeSingle: jest.fn(() => Promise.resolve({ data: { recorded_at: '2026-05-12' }, error: null })),
    then: (resolve, reject) => Promise.resolve({ data }).then(resolve, reject),
  }

  return query
}

function mockReportsQuery(data: unknown[]) {
  const reportsQuery = createReportsQuery(data)
  const marketRows = [
    { slug: 'ethereum', cmc_rank: 2, price_usd: 1, market_cap: 1, change_24h: 0, recorded_at: '2026-05-12' },
    { slug: 'bitcoin', cmc_rank: 1, price_usd: 1, market_cap: 1, change_24h: 0, recorded_at: '2026-05-12' },
    { slug: 'ethena', cmc_rank: 37, price_usd: 1, market_cap: 1, change_24h: 0, recorded_at: '2026-05-12' },
    ...data
      .map((item, index) => {
        const project = (item as { project?: { slug?: string } }).project
        if (!project?.slug) return null
        return {
          slug: project.slug,
          cmc_rank: index + 10,
          price_usd: 1,
          market_cap: 1,
          change_24h: 0,
          recorded_at: '2026-05-12',
        }
      })
      .filter(Boolean),
  ]
  const uniqueMarketRows = Array.from(
    new Map(marketRows.map((row) => [row?.slug, row])).values(),
  )
  const marketSnapshotQuery = createReportsQuery(uniqueMarketRows)

  mockCreateServerSupabaseClient.mockResolvedValue({
    from: jest.fn((table: string) => {
      if (table === 'project_reports') return reportsQuery
      if (table === 'market_data_daily') return marketSnapshotQuery

      throw new Error(`Unexpected table: ${table}`)
    }),
  })

  return reportsQuery
}

describe('ReportsPage rapid change cards', () => {
  beforeEach(() => {
    jest.clearAllMocks()
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
        slide_html_urls_by_lang: {
          en: 'https://example.com/bitcoin-forensic-en.html',
        },
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
    expect(reportsQuery.or).toHaveBeenCalledWith(expect.stringContaining('source_modified_time.gte.'))
    expect(reportsQuery.or).toHaveBeenCalledWith(expect.stringContaining('published_at.gte.'))
    expect(reportsQuery.or).toHaveBeenCalledWith(expect.stringContaining('created_at.gte.'))

    const createdAtClause = (reportsQuery.or.mock.calls[0][0] as string)
      .split(',')
      .find((clause) => clause.includes('created_at.gte.'))
    const createdAtIso = createdAtClause?.match(/created_at\.gte\.([^)]+)/)?.[1]
    expect(Number.isNaN(Date.parse(createdAtIso || ''))).toBe(false)

    expect(screen.getByText('Ethereum Forensic Analysis')).toBeTruthy()
    expect(screen.getByText('Ethereum (ETH)')).toBeTruthy()
    expect(screen.getAllByText(/Report pending/)[0].closest('a')).toBeNull()
    expect(screen.getByText('Exchange inflows and whale transfers crossed the alert threshold.')).toBeTruthy()

    expect(screen.getByText('Bitcoin Forensic Analysis')).toBeTruthy()
    expect(screen.getByText('Localized summary is used when trigger_reason is not present.')).toBeTruthy()
    expect(screen.getByRole('link', { name: /Report Details/ }).getAttribute('href')).toBe(
      '/en/reports/forensic/bitcoin?version=2&lang=en&type=forensic',
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
    expect(screen.getByText(/준비 중/).closest('a')).toBeNull()
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
    expect(screen.getByText(/준비 중/).closest('a')).toBeNull()
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
