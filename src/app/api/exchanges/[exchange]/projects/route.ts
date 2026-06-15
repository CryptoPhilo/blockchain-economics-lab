import { NextResponse, type NextRequest } from 'next/server'
import { locales, type Locale } from '@/i18n/config'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createExchangesRepository } from '@/lib/repositories/exchanges'

export const dynamic = 'force-dynamic'
export const revalidate = 0
const DEFAULT_EXCHANGE_PROJECTS_API_LOCALE: Locale = 'ko'

function toSupportedLocale(value: string | null): Locale | null {
  if (!value) return null
  const normalized = value.trim().toLowerCase().split(';')[0]?.split('-')[0] ?? ''
  return locales.includes(normalized as Locale) ? normalized as Locale : null
}

export function resolveExchangeProjectsLocale(request: NextRequest): Locale {
  const queryLocale = toSupportedLocale(request.nextUrl.searchParams.get('locale'))
  if (queryLocale) return queryLocale

  const acceptedLocales = request.headers.get('accept-language')?.split(',') ?? []
  for (const acceptedLocale of acceptedLocales) {
    const locale = toSupportedLocale(acceptedLocale)
    if (locale) return locale
  }

  return DEFAULT_EXCHANGE_PROJECTS_API_LOCALE
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ exchange: string }> },
) {
  const { exchange } = await context.params
  const locale = resolveExchangeProjectsLocale(request)

  try {
    const supabase = await createServerSupabaseClient()
    const result = await createExchangesRepository(supabase).getExchangeProjects(exchange, locale)

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
        locale,
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
