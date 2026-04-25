import { ReviewTradingSignalRpcError } from '@/lib/beta-signals-admin'

jest.mock('next/server', () => {
  class MockNextRequest {
    url: string
    method: string
    headers: Headers
    private body: unknown

    constructor(input: string, init?: { method?: string; headers?: Record<string, string>; body?: unknown }) {
      this.url = input
      this.method = init?.method ?? 'GET'
      this.headers = new Headers(init?.headers)
      this.body = init?.body
    }

    async json() {
      return this.body ?? {}
    }
  }

  return {
    NextRequest: MockNextRequest,
    NextResponse: {
      json(body: unknown, init?: { status?: number }) {
        return {
          status: init?.status ?? 200,
          async json() {
            return body
          },
        }
      },
    },
  }
})

import { NextRequest } from 'next/server'
import { withInternalBetaSignalsAccess } from './_utils'

const mockReviewSignal = jest.fn()

jest.mock('@/lib/beta-signals-admin', () => {
  const actual = jest.requireActual('@/lib/beta-signals-admin')

  return {
    ...actual,
    SupabaseBetaSignalsAdminDataSource: jest.fn().mockImplementation(() => ({
      reviewSignal: mockReviewSignal,
      getPendingReviewSignals: jest.fn(),
      getLatestApprovedSignal: jest.fn(),
    })),
  }
})

jest.mock('@/lib/supabase-admin', () => ({
  createSupabaseAdminClient: jest.fn(() => ({})),
}))

describe('withInternalBetaSignalsAccess', () => {
  beforeEach(() => {
    process.env.BETA_SIGNAL_INTERNAL_API_SECRET = 'test-secret'
    jest.spyOn(console, 'error').mockImplementation(() => {})
    mockReviewSignal.mockReset()
  })

  afterEach(() => {
    delete process.env.BETA_SIGNAL_INTERNAL_API_SECRET
    jest.restoreAllMocks()
  })

  it('maps missing trading signals to 404 while preserving detail and hint', async () => {
    mockReviewSignal.mockRejectedValue(
      new ReviewTradingSignalRpcError('rpc failed', {
        code: 'P0002',
        details: 'Trading signal 123 not found',
        hint: 'Check the signal id',
      })
    )

    const response = await withInternalBetaSignalsAccess(makeAuthorizedRequest(), async (dataSource) => {
      await dataSource.reviewSignal({ signalId: '123', action: 'approve' })
      return { ok: true }
    })

    expect(response.status).toBe(404)
    await expect(response.json()).resolves.toEqual({
      error: 'Trading signal not found',
      code: 'P0002',
      detail: 'Trading signal 123 not found',
      hint: 'Check the signal id',
    })
  })

  it('maps review conflicts to 409 when rpc errors expose a singular detail field', async () => {
    mockReviewSignal.mockRejectedValue(
      new ReviewTradingSignalRpcError('rpc failed', {
        code: 'P0001',
        detail: 'Trading signal 123 is already reviewed',
        hint: 'Refresh and retry',
      })
    )

    const response = await withInternalBetaSignalsAccess(makeAuthorizedRequest(), async (dataSource) => {
      await dataSource.reviewSignal({ signalId: '123', action: 'reject' })
      return { ok: true }
    })

    expect(response.status).toBe(409)
    await expect(response.json()).resolves.toEqual({
      error: 'Trading signal review conflict',
      code: 'P0001',
      detail: 'Trading signal 123 is already reviewed',
      hint: 'Refresh and retry',
    })
  })
})

function makeAuthorizedRequest() {
  return new NextRequest('http://localhost/api/internal/beta-signals/123/approve', {
    method: 'POST',
    headers: {
      authorization: 'Bearer test-secret',
    },
  })
}
