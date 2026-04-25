import type { SupabaseClient } from '@supabase/supabase-js'
import { createTradingSignalsAdminRepository } from '@/lib/repositories/trading-signals'
import type {
  TradingSignal,
  TradingSignalReview,
  TradingSignalReviewAction,
} from '@/lib/types'

export interface ReviewTradingSignalInput {
  signalId: string
  action: TradingSignalReviewAction
  actorId?: string
  note?: string
  metadata?: Record<string, unknown>
}

export interface ReviewTradingSignalResult {
  signal: TradingSignal
  review: TradingSignalReview
}

interface ReviewTradingSignalRpcPayload {
  signal: TradingSignal
  review: TradingSignalReview
}

interface ReviewTradingSignalRpcErrorShape {
  code?: string
  detail?: string
  details?: string
  hint?: string
  message?: string
}

export class ReviewTradingSignalRpcError extends Error {
  code?: string
  detail?: string
  hint?: string

  constructor(message: string, error?: ReviewTradingSignalRpcErrorShape | null) {
    super(message)
    this.name = 'ReviewTradingSignalRpcError'
    this.code = error?.code
    this.detail = error?.detail ?? error?.details
    this.hint = error?.hint
  }
}

export interface BetaSignalsAdminDataSource {
  getPendingReviewSignals(limit?: number): Promise<TradingSignal[]>
  getLatestApprovedSignal(projectId: string): Promise<TradingSignal | null>
  reviewSignal(input: ReviewTradingSignalInput): Promise<ReviewTradingSignalResult>
}

function normalizeReviewTradingSignalRpcPayload(
  value: unknown
): ReviewTradingSignalRpcPayload | null {
  if (!value) {
    return null
  }

  if (Array.isArray(value)) {
    const [first] = value
    return normalizeReviewTradingSignalRpcPayload(first)
  }

  if (typeof value !== 'object') {
    return null
  }

  const payload = value as Partial<ReviewTradingSignalRpcPayload>
  if (!payload.signal || !payload.review) {
    return null
  }

  return {
    signal: payload.signal,
    review: payload.review,
  }
}

export class SupabaseBetaSignalsAdminDataSource implements BetaSignalsAdminDataSource {
  private repository

  constructor(private supabase: SupabaseClient) {
    this.repository = createTradingSignalsAdminRepository(supabase)
  }

  getPendingReviewSignals(limit = 50) {
    return this.repository.getPendingReviewSignals(limit)
  }

  getLatestApprovedSignal(projectId: string) {
    return this.repository.getLatestApprovedSignal(projectId)
  }

  async reviewSignal(input: ReviewTradingSignalInput): Promise<ReviewTradingSignalResult> {
    const { data, error } = await this.supabase.rpc('review_trading_signal', {
      p_signal_id: input.signalId,
      p_action: input.action,
      p_actor_id: input.actorId ?? null,
      p_note: input.note ?? null,
      p_metadata: input.metadata ?? {},
    })

    const payload = normalizeReviewTradingSignalRpcPayload(data)

    if (error || !payload) {
      throw new ReviewTradingSignalRpcError(
        `Failed to update trading signal review state: ${error?.message ?? 'Invalid RPC response'}`,
        error
      )
    }

    return {
      signal: payload.signal,
      review: payload.review,
    }
  }
}
