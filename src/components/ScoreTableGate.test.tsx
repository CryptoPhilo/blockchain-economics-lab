import { fireEvent, render, screen } from '@testing-library/react'

import ScoreTableGate from './ScoreTableGate'

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}))

const baseReportDates = {
  econ: null,
  maturity: null,
  forensic: null,
}

function scoreRow(overrides: Partial<Parameters<typeof ScoreTableGate>[0]['rows'][number]>) {
  return {
    rank: 1,
    cmcRank: 1,
    name: 'Bitcoin',
    symbol: 'BTC',
    slug: 'bitcoin',
    change24h: 1.2,
    marketCap: 1_000_000_000,
    score: 82,
    category: 'Layer 1',
    reportTypes: ['econ', 'maturity'],
    reportDates: baseReportDates,
    ...overrides,
  }
}

describe('ScoreTableGate', () => {
  it('keeps Top500 search across the full search row set', () => {
    render(
      <ScoreTableGate
        locale="ko"
        freeLimit={500}
        currentPage={1}
        totalPages={5}
        rows={[scoreRow({ rank: 1, cmcRank: 1, name: 'Bitcoin', symbol: 'BTC', slug: 'bitcoin' })]}
        searchRows={[
          scoreRow({ rank: 1, cmcRank: 1, name: 'Bitcoin', symbol: 'BTC', slug: 'bitcoin' }),
          scoreRow({ rank: 6, cmcRank: 6, name: 'Solana', symbol: 'SOL', slug: 'solana' }),
        ]}
      />,
    )

    fireEvent.change(screen.getByRole('searchbox', { name: '종목 검색' }), {
      target: { value: 'sol' },
    })

    expect(screen.getAllByText('Solana').length).toBeGreaterThan(0)
    expect(screen.getByText('1개 검색 결과')).toBeTruthy()
    expect(screen.queryByText('Bitcoin')).toBeNull()
    expect(screen.queryByRole('link', { name: /다음/ })).toBeNull()
  })
})
