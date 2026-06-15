import Link from 'next/link'
import { notFound } from 'next/navigation'
import ScoreTableGate from '@/components/ScoreTableGate'
import type { ScoreRow } from '@/lib/score-row'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createExchangesRepository, type ExchangeRecord } from '@/lib/repositories/exchanges'

export const dynamic = 'force-dynamic'
export const revalidate = 0

function formatScore(score: unknown) {
  if (score == null) return '-'
  const numeric = Number(score)
  return Number.isFinite(numeric) ? numeric.toFixed(1) : '-'
}

function ExchangeDetailState({
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

export default async function ExchangeDetailPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>
}) {
  const { locale, slug } = await params
  const isKo = locale === 'ko'
  const supabase = await createServerSupabaseClient()
  const exchangesRepository = createExchangesRepository(supabase)
  let exchange: ExchangeRecord | null = null
  let listingRows: ScoreRow[] = []
  let bceExchangeScore: number | null = null
  let loadFailed = false

  try {
    const result = await exchangesRepository.getExchangeProjects(slug, locale)
    exchange = result.exchange
    listingRows = result.projects
    bceExchangeScore = result.bceExchangeScore
  } catch (error) {
    loadFailed = true
    console.error('Failed to load exchange listing data', {
      slug,
      message: error instanceof Error ? error.message : String(error),
    })
  }

  if (!loadFailed && !exchange) {
    notFound()
  }

  if (loadFailed || !exchange) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <ExchangeDetailState
          title={isKo ? '거래소 상세 데이터를 불러오지 못했습니다.' : 'Unable to load exchange details.'}
          description={isKo ? '잠시 후 다시 시도해 주세요.' : 'Please try again shortly.'}
        />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <section className="mb-6 rounded-2xl border border-white/10 bg-slate-950 px-6 py-8 shadow-2xl shadow-black/20 sm:px-8">
        <Link
          href={`/${locale}/exchanges`}
          className="text-sm font-medium text-cyan-300 transition-colors hover:text-cyan-200"
        >
          {isKo ? '거래소 목록' : 'Exchanges'}
        </Link>
        <div className="mt-5 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">
              {exchange.country || 'Exchange'}
            </p>
            <h1 className="mt-2 break-words text-3xl font-bold text-white sm:text-4xl">
              {exchange.name}
            </h1>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-72">
            <div className="rounded-lg border border-white/10 bg-white/[0.04] px-4 py-3">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                {isKo ? '상장 종목 수' : 'Listings'}
              </div>
              <div className="mt-1 font-mono text-xl font-semibold text-white">
                {listingRows.length}
              </div>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.04] px-4 py-3">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                BCE Exchange Score
              </div>
              <div className="mt-1 font-mono text-xl font-semibold text-white">
                {formatScore(bceExchangeScore)}
              </div>
            </div>
          </div>
        </div>
      </section>

      {listingRows.length > 0 ? (
        <ScoreTableGate
          rows={listingRows}
          freeLimit={listingRows.length}
          locale={locale}
          className="max-h-[clamp(420px,calc(100dvh-13rem),780px)] overflow-auto overscroll-y-auto pr-1"
        />
      ) : (
        <ExchangeDetailState
          title={isKo ? 'Top500 매칭 종목이 없습니다.' : 'No matched Top500 assets.'}
          description={isKo ? '이 거래소와 연결된 종목 데이터가 준비되면 기존 Top500 목록 UI로 표시됩니다.' : 'Matched assets for this exchange will appear here using the Top500 table UI.'}
        />
      )}
    </div>
  )
}
