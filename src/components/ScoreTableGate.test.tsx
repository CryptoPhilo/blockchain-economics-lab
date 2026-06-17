import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import ScoreTableGate, { type ScoreRow } from './ScoreTableGate'

const mockPush = jest.fn()

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

describe('ScoreTableGate', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders CMC rank badges and keeps project links on exchange rows', async () => {
    const rows: ScoreRow[] = [
      {
        rank: 298,
        cmcRank: 298,
        name: 'USD.AI',
        symbol: 'CHIP',
        slug: 'usd-ai',
        marketCap: 74210000,
        change24h: null,
        score: 42,
        category: '',
        reportTypes: ['econ', 'maturity'],
        reportDates: { econ: null, maturity: null, forensic: null },
      },
    ]

    render(<ScoreTableGate rows={rows} locale="ko" freeLimit={1} />)

    expect(screen.getByText('CMC #298')).toBeTruthy()
    const detailLink = screen.getByRole('link', { name: /USD\.AI/i })
    expect(detailLink.getAttribute('href')).toBe('/ko/projects/usd-ai')
    expect(screen.getByText('ECON')).toBeTruthy()
    expect(screen.getByText('MAT')).toBeTruthy()

    await userEvent.click(detailLink)
    expect(mockPush).not.toHaveBeenCalled()
  })
})
