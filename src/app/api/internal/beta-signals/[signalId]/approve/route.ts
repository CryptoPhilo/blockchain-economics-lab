import { NextRequest } from 'next/server'
import {
  parseReviewRequest,
  withInternalBetaSignalsAccess,
} from '@/app/api/internal/beta-signals/_utils'

export const dynamic = 'force-dynamic'

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ signalId: string }> },
) {
  const { signalId } = await context.params
  const reviewInput = await parseReviewRequest(request, { signalId, action: 'approve' })

  return withInternalBetaSignalsAccess(request, async (dataSource) => {
    const result = await dataSource.reviewSignal(reviewInput)
    return result
  })
}
