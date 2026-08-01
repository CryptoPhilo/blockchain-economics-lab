import { fireEvent, render, screen } from '@testing-library/react'
import type React from 'react'

import ScoreTableGate from './ScoreTableGate'

jest.mock('next/link', () => function MockLink({
  href,
  children,
  ...props
}: {
  href: string
  children: React.ReactNode
} & React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a href={href} {...props}>{children}</a>
})

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}))

function makeScoreRow(rank: number, name: string, symbol: string, slug: string) {
  return {
    rank,
    cmcRank: rank,
    name,
    symbol,
    slug,
    change24h: 0,
    marketCap: 1_000_000_000,
    score: 70,
    category: 'Infrastructure',
    reportTypes: ['econ'],
    reportDates: {
      econ: null,
      maturity: null,
      forensic: null,
    },
  }
}

describe('ScoreTableGate search', () => {
  it('filters displayed rows by asset name and symbol', () => {
    render(
      <ScoreTableGate
        rows={[
          makeScoreRow(1, 'Bitcoin', 'BTC', 'bitcoin'),
          makeScoreRow(2, 'Ethereum', 'ETH', 'ethereum'),
        ]}
        freeLimit={500}
        locale="ko"
        currentPage={1}
        totalPages={5}
      />,
    )

    fireEvent.change(screen.getByRole('searchbox', { name: '종목 검색' }), {
      target: { value: 'eth' },
    })

    expect(screen.getAllByText('Ethereum').length).toBeGreaterThan(0)
    expect(screen.queryByText('Bitcoin')).not.toBeInTheDocument()
    expect(screen.getByText('1개 검색 결과')).toBeInTheDocument()
  })

  it('uses the autocomplete index to find assets outside the current page rows', () => {
    render(
      <ScoreTableGate
        rows={[
          makeScoreRow(1, 'Bitcoin', 'BTC', 'bitcoin'),
          makeScoreRow(2, 'Ethereum', 'ETH', 'ethereum'),
        ]}
        searchRows={[
          makeScoreRow(1, 'Bitcoin', 'BTC', 'bitcoin'),
          makeScoreRow(2, 'Ethereum', 'ETH', 'ethereum'),
          makeScoreRow(26, 'Sui', 'SUI', 'sui'),
        ]}
        freeLimit={500}
        locale="ko"
        currentPage={1}
        totalPages={5}
      />,
    )

    fireEvent.change(screen.getByRole('searchbox', { name: '종목 검색' }), {
      target: { value: 'sui' },
    })

    expect(screen.getByRole('option', { name: /Sui/i })).toBeInTheDocument()
    expect(screen.getAllByText('Sui').length).toBeGreaterThan(0)
    expect(screen.queryByText('Bitcoin')).not.toBeInTheDocument()
  })
})
