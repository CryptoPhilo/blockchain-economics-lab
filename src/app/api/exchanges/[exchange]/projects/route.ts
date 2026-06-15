import { NextResponse, type NextRequest } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createExchangesRepository } from '@/lib/repositories/exchanges'

export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ exchange: string }> },
) {
  const { exchange } = await context.params

  try {
    const supabase = await createServerSupabaseClient()
    const locale = request.nextUrl.searchParams.get('locale') || 'ko'
    const result = await createExchangesRepository(supabase).getExchangeProjects(exchange, locale)

    if (!result.exchange) {
      return NextResponse.json({ error: 'Exchange not found' }, { status: 404 })
    }

    return NextResponse.json({
      exchange: result.exchange,
      data: result.projects,
      rules: {
        detailFilter: 'Path segment matches exchange slug or exact exchange name, case-insensitive.',
        rowShape: 'Project rows match the existing Top500 score table fields: rank, name, symbol, slug, marketCap, score, category, reportTypes, reportDates.',
      },
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch exchange projects' },
      { status: 500 },
    )
  }
}
