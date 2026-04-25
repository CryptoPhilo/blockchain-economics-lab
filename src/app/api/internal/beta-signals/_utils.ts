import { NextRequest, NextResponse } from 'next/server'
import {
  SupabaseBetaSignalsAdminDataSource,
  type BetaSignalsAdminDataSource,
  type ReviewTradingSignalInput,
} from '@/lib/beta-signals-admin'
import {
  getInternalApiSecret,
  isInternalApiRouteEnabled,
  isAuthorizedInternalApiRequest,
} from '@/lib/internal-api-auth'
import { createSupabaseAdminClient } from '@/lib/supabase-admin'

export const dynamic = 'force-dynamic'

type GuardedHandler<T> = (dataSource: BetaSignalsAdminDataSource) => Promise<T>

interface InternalApiErrorShape {
  code?: string
  detail?: string
  details?: string
  hint?: string
  message?: string
}

interface ReviewRequestBody {
  actorId?: string
  note?: string
  metadata?: Record<string, unknown>
}

export async function withInternalBetaSignalsAccess<T>(request: NextRequest, handler: GuardedHandler<T>) {
  if (!isInternalApiRouteEnabled()) {
    return NextResponse.json({ error: 'Not Found' }, { status: 404 })
  }

  const secret = getInternalApiSecret()

  if (!secret) {
    return NextResponse.json({ error: 'Service Unavailable' }, { status: 503 })
  }

  if (!isAuthorizedInternalApiRequest(request, secret)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const dataSource = new SupabaseBetaSignalsAdminDataSource(createSupabaseAdminClient())
    const payload = await handler(dataSource)
    if (payload instanceof Response) {
      return payload
    }
    return NextResponse.json(payload)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Internal server error'
    console.error('[BetaSignals][InternalAPI]', message)
    const mappedError = mapInternalApiError(error)
    return NextResponse.json(mappedError.body, { status: mappedError.status })
  }
}

export function parsePositiveLimit(value: string | null, fallback = 50) {
  if (!value) {
    return fallback
  }

  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed) || parsed < 1) {
    return null
  }

  return Math.min(parsed, 100)
}

export async function parseReviewRequest(
  request: NextRequest,
  input: Pick<ReviewTradingSignalInput, 'signalId' | 'action'>,
) {
  let body: ReviewRequestBody = {}

  try {
    body = await request.json()
  } catch {}

  return {
    ...input,
    actorId: typeof body.actorId === 'string' && body.actorId.length > 0 ? body.actorId : undefined,
    note: typeof body.note === 'string' && body.note.length > 0 ? body.note : undefined,
    metadata: isRecord(body.metadata) ? body.metadata : undefined,
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function mapInternalApiError(error: unknown) {
  const apiError = isInternalApiErrorShape(error) ? error : null
  const code = apiError?.code
  const detail = apiError?.detail ?? apiError?.details
  const hint = apiError?.hint
  const message =
    error instanceof Error
      ? error.message
      : typeof apiError?.message === 'string'
        ? apiError.message
        : 'Internal server error'

  if (code === 'P0002') {
    return {
      status: 404,
      body: {
        error: 'Trading signal not found',
        code,
        detail: detail ?? message,
        hint,
      },
    }
  }

  if (code === 'P0001') {
    return {
      status: 409,
      body: {
        error: 'Trading signal review conflict',
        code,
        detail: detail ?? message,
        hint,
      },
    }
  }

  return {
    status: 500,
    body: {
      error: 'Internal server error',
      code,
      detail: detail ?? message,
      hint,
    },
  }
}

function isInternalApiErrorShape(value: unknown): value is InternalApiErrorShape {
  return typeof value === 'object' && value !== null
}
