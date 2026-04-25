import { NextRequest, NextResponse } from 'next/server'
import {
  withInternalBetaSignalsAccess,
} from '@/app/api/internal/beta-signals/_utils'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const projectId = request.nextUrl.searchParams.get('projectId')

  if (!projectId) {
    return NextResponse.json({ error: 'projectId is required' }, { status: 400 })
  }

  return withInternalBetaSignalsAccess(request, async (dataSource) => {
    const signal = await dataSource.getLatestApprovedSignal(projectId)

    if (!signal) {
      return NextResponse.json({ error: 'No approved signal found' }, { status: 404 })
    }

    return {
      signal,
    }
  })
}
