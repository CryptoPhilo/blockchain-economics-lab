/**
 * @jest-environment node
 */

import { NextRequest } from 'next/server'
import { GET, resolveExchangeProjectsLocale } from './route'
import { createExchangesRepository } from '@/lib/repositories/exchanges'

jest.mock('@/lib/supabase-server', () => ({
  createServerSupabaseClient: jest.fn(async () => ({ from: jest.fn() })),
}))

jest.mock('@/lib/repositories/exchanges', () => ({
  createExchangesRepository: jest.fn(),
}))

const getExchangeProjects = jest.fn()

function request(url: string, init?: ConstructorParameters<typeof NextRequest>[1]) {
  return new NextRequest(url, init)
}

describe('/api/exchanges/[exchange]/projects route', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(createExchangesRepository as jest.Mock).mockReturnValue({
      getExchangeProjects,
    })
    getExchangeProjects.mockResolvedValue({
      exchange: { slug: 'binance', name: 'Binance' },
      bceExchangeScore: 66.01,
      bceExchangeScoreFormulaVersion: 'bce-exchange-score-v1',
      bceExchangeScoreComponents: {},
      projects: [],
    })
  })

  it('passes an explicit query locale into the exchange repository', async () => {
    const response = await GET(
      request('https://www.bcelab.xyz/api/exchanges/binance/projects?locale=ja'),
      { params: Promise.resolve({ exchange: 'binance' }) },
    )

    expect(response.status).toBe(200)
    expect(getExchangeProjects).toHaveBeenCalledWith('binance', 'ja')
    await expect(response.json()).resolves.toEqual(expect.objectContaining({
      rules: expect.objectContaining({ locale: 'ja' }),
    }))
  })

  it('keeps the bare API evidence path on a locale-aware fallback', async () => {
    const locale = resolveExchangeProjectsLocale(request('https://www.bcelab.xyz/api/exchanges/binance/projects'))

    expect(locale).toBe('ko')
  })

  it('uses Accept-Language when no query locale is provided', async () => {
    const locale = resolveExchangeProjectsLocale(request(
      'https://www.bcelab.xyz/api/exchanges/binance/projects',
      { headers: { 'accept-language': 'fr-FR,fr;q=0.9,en;q=0.8' } },
    ))

    expect(locale).toBe('fr')
  })
})
