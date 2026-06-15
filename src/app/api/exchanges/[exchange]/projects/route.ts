import { NextResponse, type NextRequest } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createExchangesRepository } from '@/lib/repositories/exchanges'

export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ exchange: string }> },
) {
  const { exchange } = await context.params

  try {
    const supabase = await createServerSupabaseClient()
    const result = await createExchangesRepository(supabase).getExchangeProjects(exchange)

    if (!result.exchange) {
      return NextResponse.json({ error: 'Exchange not found' }, { status: 404 })
    }

    return NextResponse.json({
      exchange: result.exchange,
      bceExchangeScore: result.bceExchangeScore,
      bceExchangeScoreFormulaVersion: result.bceExchangeScoreFormulaVersion,
      bceExchangeScoreComponents: result.bceExchangeScoreComponents,
      data: result.projects,
      rules: {
        detailFilter: 'Path segment matches exchange slug or exact exchange name, case-insensitive.',
        rowShape: 'Project rows match the existing Top500 score table fields: rank, name, symbol, slug, marketCap, score, category, reportTypes, reportDates.',
        bceExchangeScore: 'Exchange-level aggregate uses bce-exchange-score-v1 and is separate from per-project BCE Score row values.',
      },
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch exchange projects' },
      { status: 500 },
    )
  }
}
