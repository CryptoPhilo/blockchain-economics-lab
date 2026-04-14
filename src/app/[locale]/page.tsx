import { getTranslations } from 'next-intl/server'
import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocalizedField, type Locale } from '@/lib/types'
import ProductCard from '@/components/ProductCard'
import DisclaimerBanner from '@/components/DisclaimerBanner'
import ForensicTickerBar from '@/components/ForensicTickerBar'
import ForensicAlertSection from '@/components/ForensicAlertSection'

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t = await getTranslations()
  const isKo = locale === 'ko'

  let featuredProducts: any[] = []
  let categories: any[] = []
  let trackedProjects: any[] = []

  try {
    const supabase = await createServerSupabaseClient()
    const [productsRes, categoriesRes, projectsRes] = await Promise.all([
      supabase
        .from('products')
        .select('*, category:categories(*)')
        .eq('status', 'published')
        .eq('featured', true)
        .order('published_at', { ascending: false })
        .limit(4),
      supabase
        .from('categories')
        .select('*')
        .order('sort_order'),
      supabase
        .from('tracked_projects')
        .select('id, name, slug, symbol, maturity_score, threat_level, chain, category')
        .in('status', ['active', 'monitoring_only'])
        .order('maturity_score', { ascending: false, nullsFirst: false })
        .limit(9),
    ])
    featuredProducts = productsRes.data || []
    categories = categoriesRes.data || []
    trackedProjects = projectsRes.data || []
  } catch (e) {
    console.error('Failed to fetch data:', e)
  }

  return (
    <div>
      {/* Forensic Alert Ticker — scrolling red bar at the very top */}
      <ForensicTickerBar />

      {/* Hero Section — 360° Project Intelligence */}
      <section className="relative overflow-hidden bg-gradient-to-br from-gray-950 via-indigo-950 to-gray-950 py-24 px-6">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm mb-8">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
            360° Project Intelligence
          </div>
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-indigo-400 bg-clip-text text-transparent mb-6">
            {isKo
              ? '경제 설계 · 성숙도 · 리스크\n한 곳에서'
              : 'Economics · Maturity · Risk\nAll in One Place'}
          </h1>
          <p className="text-xl text-gray-400 max-w-3xl mx-auto mb-4">
            {isKo
              ? 'Delphi급 분석을 1/20 가격에. AI 연구 에이전트가 생산하는 7개 언어 보고서.'
              : 'Delphi-grade analysis at 1/20th the price. AI-powered reports in 7 languages.'}
          </p>
          <p className="text-sm text-gray-500 max-w-2xl mx-auto mb-10">
            {isKo
              ? '토큰노믹스 분석, 성숙도 평가, 포렌식 리스크 — 단일 프로젝트에 대한 360° 인텔리전스를 하나의 구독으로.'
              : 'Tokenomics analysis, maturity assessment, forensic risk — 360° intelligence for every project, in one subscription.'}
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Link
              href={`/${locale}/score`}
              className="px-8 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40"
            >
              {isKo ? '프로젝트 점수 조회' : 'Lookup Project Scores'}
            </Link>
            <Link
              href={`/${locale}/subscribe`}
              className="px-8 py-3.5 bg-white/5 hover:bg-white/10 text-white font-semibold rounded-xl border border-white/10 transition-all"
            >
              {isKo ? '무료 뉴스레터 구독' : 'Free Newsletter'}
            </Link>
          </div>
        </div>

        {/* 3 Report Types */}
        <div className="relative max-w-4xl mx-auto mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            {
              icon: '📊',
              type: 'ECON',
              title: isKo ? '경제 설계 분석' : 'Economic Design',
              desc: isKo ? '토크노믹스, 가치 축적, 인센티브 설계' : 'Tokenomics, value accrual, incentive design',
              price: '$49',
              color: 'from-blue-500/10 to-blue-600/5 border-blue-500/20',
            },
            {
              icon: '📈',
              type: 'MAT',
              title: isKo ? '성숙도 평가' : 'Maturity Assessment',
              desc: isKo ? '7축 BCE Score™, 내러티브 건강도' : '7-axis BCE Score™, narrative health',
              price: '$39',
              color: 'from-green-500/10 to-green-600/5 border-green-500/20',
            },
            {
              icon: '🔍',
              type: 'FOR',
              title: isKo ? '포렌식 리스크' : 'Forensic Risk',
              desc: isKo ? '온체인 포렌식, 5단계 위협 평가' : 'On-chain forensics, 5-level threat assessment',
              price: '$29',
              color: 'from-red-500/10 to-red-600/5 border-red-500/20',
            },
          ].map((report) => (
            <div
              key={report.type}
              className={`p-6 rounded-xl bg-gradient-to-br ${report.color} border text-center`}
            >
              <span className="text-3xl">{report.icon}</span>
              <div className="text-xs font-mono text-gray-500 mt-2">{report.type}</div>
              <h3 className="font-bold text-white mt-2">{report.title}</h3>
              <p className="text-xs text-gray-400 mt-2">{report.desc}</p>
              <p className="text-lg font-bold text-indigo-400 mt-3">{report.price}</p>
            </div>
          ))}
        </div>

        {/* Stats */}
        <div className="relative max-w-4xl mx-auto mt-12 grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { value: '7', label: isKo ? '개 언어' : 'Languages' },
            { value: '360°', label: isKo ? '통합 인텔리전스' : 'Intelligence' },
            { value: '$19', label: isKo ? '월 구독' : '/mo All Access' },
            { value: 'AI', label: isKo ? '에이전트 구동' : 'Agent Powered' },
          ].map((stat) => (
            <div key={stat.label} className="text-center p-4 rounded-xl bg-white/5 border border-white/5">
              <div className="text-2xl font-bold text-indigo-400">{stat.value}</div>
              <div className="text-sm text-gray-500 mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Latest Forensic Alerts — card previews with risk gauge */}
      <ForensicAlertSection />

      {/* Tracked Projects Scores */}
      {trackedProjects.length > 0 && (
        <section className="max-w-6xl mx-auto px-6 py-20">
          <div className="flex justify-between items-center mb-10">
            <div>
              <h2 className="text-3xl font-bold text-white">BCE Maturity Score™</h2>
              <p className="text-gray-500 mt-2">
                {isKo ? '추적 프로젝트 실시간 성숙도 점수' : 'Live maturity scores for tracked projects'}
              </p>
            </div>
            <Link href={`/${locale}/score`} className="text-indigo-400 hover:text-indigo-300 transition-colors">
              {isKo ? '전체 보기' : 'View All'} →
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {trackedProjects.map((p) => {
              const score = p.maturity_score || 0
              const scoreColor = score >= 80 ? 'text-green-400' : score >= 60 ? 'text-yellow-400' : score >= 40 ? 'text-orange-400' : 'text-red-400'
              const threatEmoji = p.threat_level === 'critical' ? '⚫' : p.threat_level === 'warning' ? '🔴' : p.threat_level === 'caution' ? '🟠' : p.threat_level === 'watch' ? '🟡' : '🟢'

              return (
                <Link
                  key={p.id}
                  href={`/${locale}/score?project=${p.slug}`}
                  className="p-5 rounded-xl bg-white/5 border border-white/5 hover:border-indigo-500/20 hover:bg-white/10 transition-all group"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-white group-hover:text-indigo-400 transition-colors">
                        {p.name}
                      </h3>
                      <p className="text-xs text-gray-500 mt-1">{p.symbol} · {p.chain}</p>
                    </div>
                    <div className="text-right">
                      <div className={`text-2xl font-bold ${scoreColor}`}>{score.toFixed(1)}</div>
                      <div className="text-xs mt-1">{threatEmoji}</div>
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
          <div className="flex justify-center mt-8">
            <Link
              href={`/${locale}/projects`}
              className="px-6 py-3 bg-white/5 hover:bg-white/10 text-indigo-400 hover:text-indigo-300 font-medium rounded-xl border border-white/10 hover:border-indigo-500/30 transition-all"
            >
              {isKo ? '전체 프로젝트 보기' : 'View All Projects'} →
            </Link>
          </div>
        </section>
      )}

      {/* View All Reports CTA */}
      <section className="max-w-6xl mx-auto px-6 pb-4">
        <div className="flex justify-center">
          <Link
            href={`/${locale}/reports`}
            className="px-6 py-3 bg-white/5 hover:bg-white/10 text-indigo-400 hover:text-indigo-300 font-medium rounded-xl border border-white/10 hover:border-indigo-500/30 transition-all"
          >
            {isKo ? '전체 보고서 보기' : 'Browse All Reports'} →
          </Link>
        </div>
      </section>

      {/* Categories */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold mb-10">{isKo ? '연구 분야' : 'Research Domains'}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {categories?.map((cat) => (
            <Link
              key={cat.id}
              href={`/${locale}/products?category=${cat.slug}`}
              className="p-6 rounded-xl bg-white/5 border border-white/5 hover:border-indigo-500/30 hover:bg-indigo-500/5 transition-all group"
            >
              <div className="text-3xl mb-3">{cat.icon}</div>
              <h3 className="font-semibold text-white group-hover:text-indigo-400 transition-colors">
                {getLocalizedField(cat, 'name', locale as Locale)}
              </h3>
              <p className="text-sm text-gray-500 mt-2 line-clamp-2">
                {getLocalizedField(cat, 'description', locale as Locale)}
              </p>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured Products */}
      {featuredProducts.length > 0 && (
        <section className="max-w-6xl mx-auto px-6 pb-20">
          <div className="flex justify-between items-center mb-10">
            <h2 className="text-3xl font-bold">{t('products.featured')}</h2>
            <Link href={`/${locale}/products`} className="text-indigo-400 hover:text-indigo-300 transition-colors">
              {t('common.viewAll')} →
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {featuredProducts.map((product) => (
              <ProductCard key={product.id} product={product} locale={locale as Locale} />
            ))}
          </div>
        </section>
      )}

      {/* Newsletter CTA */}
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <div className="rounded-2xl bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 p-10 text-center">
          <h3 className="text-2xl font-bold mb-4">
            {isKo ? '무료 리서치 뉴스레터' : 'Free Research Newsletter'}
          </h3>
          <p className="text-gray-400 mb-6">
            {isKo
              ? '매주 AI 기반 시장 분석과 프로젝트 인텔리전스를 받아보세요'
              : 'Weekly AI-powered market analysis and project intelligence delivered to your inbox'}
          </p>
          <div className="flex justify-center gap-4 flex-wrap">
            <Link
              href={`/${locale}/subscribe`}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/25"
            >
              {isKo ? '무료 구독하기' : 'Subscribe Free'} →
            </Link>
          </div>
          <div className="flex justify-center gap-8 mt-6 text-sm text-gray-500">
            <span>📊 Weekly Market Pulse</span>
            <span>🔍 Deep Dive Preview</span>
            <span>🚨 Forensic Alerts</span>
          </div>
        </div>
      </section>

      {/* Crypto Payment Banner */}
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <div className="rounded-2xl bg-gradient-to-r from-green-500/5 to-emerald-500/5 border border-green-500/10 p-8 text-center">
          <h3 className="text-xl font-bold mb-3">Crypto-Native Payments</h3>
          <p className="text-gray-400 text-sm mb-4">{isKo ? 'BTC, ETH, USDT, USDC 결제 지원' : 'Pay with BTC, ETH, USDT, USDC'}</p>
          <div className="flex justify-center gap-6 text-3xl">
            <span title="Bitcoin">₿</span>
            <span title="Ethereum">Ξ</span>
            <span title="USDT">₮</span>
            <span title="USDC">💲</span>
          </div>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="max-w-6xl mx-auto px-6 pb-10">
        <DisclaimerBanner />
      </section>
    </div>
  )
}
