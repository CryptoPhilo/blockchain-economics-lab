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
        averageBceScore: 'Average of non-null tracked_projects.maturity_score values only; null when no listed project has a score.',
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
