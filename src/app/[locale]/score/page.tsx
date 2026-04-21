import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { fetchCoinGeckoPrices } from '@/lib/coingecko'
import { fetchCMCPricesByIds } from '@/lib/coinmarketcap'
import ScoreTableGate from '@/components/ScoreTableGate'
import SubscribeForm from '@/components/SubscribeForm'
import Link from 'next/link'

/**
 * CMC-Style Market Cap Ranking Page + Report Badges (BCE-379)
 *
 * Shows top 200 projects by market cap across 2 pages (100 per page).
 * Each row includes price, 24h change, market cap, BCE Score, and report badges.
 * Data: tracked_projects (DB) + CoinGecko API (real-time price/market data).
 */

const ITEMS_PER_PAGE = 100
const MAX_RANK = 200

export default async function ScorePage({
  params,
  searchParams
}: {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ page?: string }>
}) {
  const { locale } = await params
  const { page: pageStr } = await searchParams
  const t = await getTranslations()
  const supabase = await createServerSupabaseClient()

  const currentPage = Math.max(1, Math.min(2, parseInt(pageStr || '1', 10)))

  // Fetch all active tracked projects (including cmc_id for fallback)
  const { data: projects } = await supabase
    .from('tracked_projects')
    .select(`
      id, name, slug, symbol, category,
      market_cap_usd, coingecko_id, cmc_id, maturity_score,
      last_econ_report_at, last_maturity_report_at, last_forensic_report_at
    `)
    .in('status', ['active', 'monitoring_only'])
    .order('market_cap_usd', { ascending: false, nullsFirst: false })

  const allProjects = projects || []

  // Waterfall approach: CoinGecko → CoinMarketCap → DB cache

  // Step 1: Fetch CoinGecko data for all projects with coingecko_id
  const coingeckoIds = allProjects
    .map((p) => p.coingecko_id)
    .filter((id): id is string => !!id)

  const cgPriceData = await fetchCoinGeckoPrices([...new Set(coingeckoIds)])

  // Step 2: Identify projects without CoinGecko data and fetch from CMC
  const projectsNeedingCMC = allProjects.filter(
    (p) => p.cmc_id && (!p.coingecko_id || !cgPriceData[p.coingecko_id])
  )

  const cmcIds = projectsNeedingCMC
    .map((p) => p.cmc_id)
    .filter((id): id is number => typeof id === 'number' && id > 0)

  const cmcPriceData = await fetchCMCPricesByIds([...new Set(cmcIds)])

  // Step 3: Merge price data (CoinGecko takes precedence)
  const priceData = { ...cgPriceData }

  // Build ranked rows by market cap (waterfall: CoinGecko → CMC → DB)
  // BCE-379: Limit to top 200 projects across 2 pages
  const allRows = allProjects
    .map((p) => {
      // Try CoinGecko first, then CMC, then DB
      const cgData = p.coingecko_id ? priceData[p.coingecko_id] : undefined
      const cmcData = p.cmc_id ? cmcPriceData[p.cmc_id] : undefined
      const liveData = cgData || cmcData

      const marketCap = liveData?.usd_market_cap || p.market_cap_usd || 0

      const reportTypes: string[] = []
      if (p.last_econ_report_at) reportTypes.push('econ')
      if (p.last_maturity_report_at) reportTypes.push('maturity')
      if (p.last_forensic_report_at) reportTypes.push('forensic')

      return {
        name: p.name,
        symbol: p.symbol,
        slug: p.slug,
        price: liveData?.usd ?? null,
        change24h: liveData?.usd_24h_change ?? null,
        marketCap,
        score: p.maturity_score ?? null,
        category: p.category || '',
        reportTypes,
        reportDates: {
          econ: p.last_econ_report_at,
          maturity: p.last_maturity_report_at,
          forensic: p.last_forensic_report_at,
        },
      }
    })
    .sort((a, b) => b.marketCap - a.marketCap)
    .slice(0, MAX_RANK) // Top 200 only
    .map((row, i) => ({ ...row, rank: i + 1 }))

  // Paginate: 100 per page
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE
  const endIdx = startIdx + ITEMS_PER_PAGE
  const rows = allRows.slice(startIdx, endIdx)
  const totalPages = Math.ceil(Math.min(allRows.length, MAX_RANK) / ITEMS_PER_PAGE)

  const isKo = locale === 'ko'

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-bold mb-3">
          {isKo ? '리포트' : 'Report'}
        </h1>
        <p className="text-gray-400 max-w-xl mx-auto">
          {isKo
            ? '시가총액 200위 종목들의 BCE 보고서를 확인하세요'
            : 'Crypto project rankings by market cap with BCE analysis reports'}
        </p>
      </div>

      {/* Page indicator */}
      {totalPages > 1 && (
        <div className="mb-4 text-center">
          <span className="text-sm text-gray-400">
            {isKo
              ? `${startIdx + 1}-${Math.min(endIdx, allRows.length)}위 (전체 ${allRows.length}개 프로젝트)`
              : `Rank ${startIdx + 1}-${Math.min(endIdx, allRows.length)} of ${allRows.length} projects`}
          </span>
        </div>
      )}

      {/* Market cap ranking table with email gate */}
      {rows.length > 0 ? (
        <ScoreTableGate rows={rows} freeLimit={200} locale={locale} />
      ) : (
        <div className="text-center py-20">
          <p className="text-gray-500 text-lg">
            {isKo ? '아직 프로젝트 데이터가 없습니다.' : 'No project data available yet.'}
          </p>
          <p className="text-gray-600 text-sm mt-2">
            {isKo ? '프로젝트가 등록되면 여기에 표시됩니다.' : 'Rankings will appear here once projects are tracked.'}
          </p>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <nav className="flex items-center justify-center gap-4 mt-8">
          {currentPage > 1 && (
            <Link
              href={`/${locale}/score?page=${currentPage - 1}`}
              className="px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white text-sm font-medium transition-colors"
            >
              ← {isKo ? '이전 (1-100위)' : 'Previous (1-100)'}
            </Link>
          )}
          <div className="flex gap-2">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <Link
                key={page}
                href={`/${locale}/score?page=${page}`}
                className={`px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  page === currentPage
                    ? 'bg-indigo-500 text-white'
                    : 'bg-white/5 hover:bg-white/10 text-gray-400'
                }`}
              >
                {page}
              </Link>
            ))}
          </div>
          {currentPage < totalPages && (
            <Link
              href={`/${locale}/score?page=${currentPage + 1}`}
              className="px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white text-sm font-medium transition-colors"
            >
              {isKo ? '다음 (101-200위)' : 'Next (101-200)'} →
            </Link>
          )}
        </nav>
      )}

      {/* Newsletter CTA */}
      <div className="mt-16 p-8 rounded-2xl bg-gradient-to-r from-indigo-500/5 to-purple-500/5 border border-indigo-500/15 text-center">
        <h3 className="text-xl font-bold mb-2">
          {isKo ? '시장 업데이트 알림 받기' : 'Get Market Update Alerts'}
        </h3>
        <p className="text-gray-400 text-sm mb-4">
          {isKo
            ? '새로운 보고서와 시장 변동 알림을 받아보세요'
            : 'Be the first to know about new reports and market movements'}
        </p>
        <SubscribeForm
          locale={locale}
          source="newsletter"
          translations={{
            placeholder: t('subscribe.emailPlaceholder'),
            cta: t('subscribe.cta'),
            success: t('subscribe.checkEmail'),
          }}
        />
      </div>

      {/* Stats */}
      <div className="mt-10 pt-6 border-t border-white/5 flex justify-center gap-8 text-sm text-gray-600">
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{allRows.length}</div>
          <div>{isKo ? '상위 프로젝트' : 'Top Projects'}</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white">
            {allRows.filter((r) => r.reportTypes.length > 0).length}
          </div>
          <div>{isKo ? '분석 보고서' : 'Reports'}</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{totalPages}</div>
          <div>{isKo ? '페이지' : 'Pages'}</div>
        </div>
      </div>
    </div>
  )
}
