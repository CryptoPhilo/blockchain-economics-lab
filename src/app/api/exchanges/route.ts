import { NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createExchangesRepository } from '@/lib/repositories/exchanges'

export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET() {
  try {
    const supabase = await createServerSupabaseClient()
    const exchanges = await createExchangesRepository(supabase).getExchangeAggregates()

    return NextResponse.json({
      data: exchanges,
      rules: {
        listingCount: 'Distinct active projects with active exchange listings only.',
        bceExchangeScore: 'BCE Exchange Score uses formula version bce-exchange-score-v1 and returns null when the exchange has no DB-matched listed projects.',
        bceExchangeScoreComponents: 'Components are coreBceQuality, rankQuality, scoreCoverage, longTailPenalty, listedProjectCount, scoredProjectCount, and longTailRatio.',
        duplicates: 'exchange_project_listings has a UNIQUE(exchange_id, project_id) constraint; API aggregation also deduplicates project IDs.',
        inactiveAndDelisted: 'Inactive exchanges, inactive/delisted listings, and archived/suspended projects are excluded.',
      },
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch exchanges' },
      { status: 500 },
    )
  }
}
