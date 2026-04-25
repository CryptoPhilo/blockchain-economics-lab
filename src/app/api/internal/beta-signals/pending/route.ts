import { NextRequest, NextResponse } from 'next/server'
import {
  parsePositiveLimit,
  withInternalBetaSignalsAccess,
} from '@/app/api/internal/beta-signals/_utils'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const limit = parsePositiveLimit(request.nextUrl.searchParams.get('limit'))

  if (limit === null) {
    return NextResponse.json({ error: 'limit must be a positive integer' }, { status: 400 })
  }

  return withInternalBetaSignalsAccess(request, async (dataSource) => {
    const items = await dataSource.getPendingReviewSignals(limit)

    return {
      items,
      count: items.length,
      limit,
    }
  })
}
