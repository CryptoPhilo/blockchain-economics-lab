import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createExchangesRepository, type ExchangeAggregate } from '@/lib/repositories/exchanges'
import { getExchangesHeaderStyle } from '@/lib/exchange-header-art'

export const dynamic = 'force-dynamic'
export const revalidate = 0

function formatScore(score: unknown) {
  if (score == null) return '-'
  const numeric = Number(score)
  return Number.isFinite(numeric) ? numeric.toFixed(1) : '-'
}

function ExchangeState({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-6 py-14 text-center">
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-400">{description}</p>
    </div>
  )
}

export default async function ExchangesPage({
  params,
}: {
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  const isKo = locale === 'ko'
  let rows: ExchangeAggregate[] = []
  let loadFailed = false

  try {
    const supabase = await createServerSupabaseClient()
    rows = await createExchangesRepository(supabase).getExchangeAggregates()
  } catch (error) {
    loadFailed = true
    console.error('Failed to render exchanges page', {
      message: error instanceof Error ? error.message : String(error),
    })
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <section
        className="relative mb-6 overflow-hidden rounded-2xl border border-white/10 bg-slate-950 bg-cover bg-center px-6 py-14 shadow-2xl shadow-black/30 sm:px-8 sm:py-16"
        style={getExchangesHeaderStyle()}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.08),transparent_38%)]" />
        <div className="relative max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">Exchanges</p>
          <h1 className="mt-3 text-3xl font-bold text-white drop-shadow-[0_2px_18px_rgba(0,0,0,0.8)] sm:text-4xl">
            {isKo ? '거래소' : 'Exchanges'}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-200 drop-shadow-[0_2px_14px_rgba(0,0,0,0.72)] sm:text-base">
            {isKo
              ? '주요 거래소의 상장 종목 수와 BCE Exchange Score를 한눈에 확인하세요.'
              : 'Review major exchanges with listed-asset counts and BCE Exchange Scores.'}
          </p>
        </div>
      </section>

      {loadFailed ? (
        <ExchangeState
          title={isKo ? '거래소 데이터를 불러오지 못했습니다.' : 'Unable to load exchange data.'}
          description={isKo ? '잠시 후 다시 시도해 주세요.' : 'Please try again shortly.'}
        />
      ) : rows.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]">
          <div className="grid grid-cols-[minmax(0,1fr)_7rem_6rem] gap-3 border-b border-white/10 bg-white/[0.04] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500 sm:grid-cols-[minmax(0,1fr)_10rem_8rem]">
            <div>{isKo ? '거래소명' : 'Exchange'}</div>
            <div className="text-right">{isKo ? '상장 종목 수' : 'Listings'}</div>
            <div className="text-right">BCE Exchange Score</div>
          </div>
          <div className="divide-y divide-white/5">
            {rows.map((exchange) => (
              <Link
                key={exchange.id}
                href={`/${locale}/exchanges/${exchange.slug}`}
                className="grid grid-cols-[minmax(0,1fr)_7rem_6rem] items-center gap-3 px-4 py-4 transition-colors hover:bg-white/[0.05] sm:grid-cols-[minmax(0,1fr)_10rem_8rem]"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-white sm:text-base" title={exchange.name}>
                    {exchange.name}
                  </div>
                  <div className="mt-1 truncate text-xs font-medium uppercase text-slate-500">
                    {exchange.country || exchange.slug}
                  </div>
                </div>
                <div className="text-right font-mono text-sm text-slate-200">{exchange.listedProjectCount}</div>
                <div className="text-right">
                  {formatScore(exchange.bceExchangeScore) === '-' ? (
                    <span className="text-sm text-slate-600">-</span>
                  ) : (
                    <span className="inline-flex rounded bg-cyan-500/10 px-2 py-0.5 text-xs font-bold text-cyan-300">
                      {formatScore(exchange.bceExchangeScore)}
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      ) : (
        <ExchangeState
          title={isKo ? '표시할 거래소가 없습니다.' : 'No exchanges available.'}
          description={isKo ? '거래소 상장 관계 데이터가 등록되면 여기에 표시됩니다.' : 'Exchange listing relationships will appear here after they are tracked.'}
        />
      )}
    </div>
  )
}
