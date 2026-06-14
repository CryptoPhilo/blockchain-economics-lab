import { render, screen } from '@testing-library/react'

import Header from './Header'

jest.mock('next/navigation', () => ({
  usePathname: () => '/ko/score',
}))

jest.mock('next-intl', () => ({
  useLocale: () => 'ko',
  useTranslations: () => (key: string) => ({
    siteName: '블록체인 경제 연구소',
    reports: '급변동 종목',
    score: '리포트',
    signIn: '로그인',
  }[key] || key),
}))

describe('Header', () => {
  it('keeps the restored BCE shell with only the two production nav items', () => {
    render(<Header />)

    expect(screen.getByText('BCE Lab')).toBeInTheDocument()
    expect(screen.getByText('블록체인 경제 연구소')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /급변동 종목/ })).toHaveAttribute('href', '/ko/reports')
    expect(screen.getByRole('link', { name: /리포트/ })).toHaveAttribute('href', '/ko/score')

    expect(screen.queryByRole('link', { name: /상품/ })).toBeNull()
    expect(screen.queryByRole('link', { name: /뉴스레터/ })).toBeNull()
    expect(screen.queryByRole('link', { name: /대시보드/ })).toBeNull()
  })
})
