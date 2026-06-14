import { render, screen } from '@testing-library/react'

import Footer from './Footer'

jest.mock('next-intl', () => ({
  useLocale: () => 'ko',
  useTranslations: (namespace: string) => (key: string) => {
    const messages: Record<string, Record<string, string>> = {
      common: {
        siteName: '블록체인 경제 연구소',
      },
      footer: {
        aboutText: '블록체인 경제 연구소는 AI 에이전트가 구동하는 프로젝트 인텔리전스를 제공합니다.',
        research: '연구',
        legal: '법률',
        privacy: '개인정보보호정책',
        terms: '이용약관',
        contact: '연락처',
        copyright: '© 2026 블록체인 경제 연구소. 모든 권리 보유.',
      },
    }

    return messages[namespace]?.[key] || key
  },
}))

describe('Footer', () => {
  it('uses the restored BCE brand block and does not resurrect the dead newsletter form', () => {
    render(<Footer />)

    expect(screen.getByText('BCE Lab')).toBeTruthy()
    expect(screen.getByText('블록체인 경제 연구소')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Rapid Change Items' }).getAttribute('href')).toBe('/ko/reports')
    expect(screen.getByRole('link', { name: 'Report Rankings' }).getAttribute('href')).toBe('/ko/score')

    expect(screen.queryByText('뉴스레터')).toBeNull()
    expect(screen.queryByPlaceholderText('이메일을 입력하세요')).toBeNull()
    expect(screen.queryByRole('button', { name: /구독/ })).toBeNull()
  })
})
