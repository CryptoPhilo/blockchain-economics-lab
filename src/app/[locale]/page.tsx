import { getTranslations } from 'next-intl/server'
import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocalizedField, type Locale } from '@/lib/types'
import ProductCard from '@/components/ProductCard'
import DisclaimerBanner from '@/components/DisclaimerBanner'
import ForensicSlideCards from '@/components/ForensicSlideCards'

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t = await getTranslations()

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let featuredProducts: any[] = []
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let categories: any[] = []
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let trackedProjects: any[] = []
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let forensicReports: any[] = []

  try {
    const supabase = await createServerSupabaseClient()
    const [productsRes, categoriesRes, projectsRes, forensicRes] = await Promise.all([
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
      supabase
        .from('project_reports')
        .select(`
          id, project_id, risk_level,
          card_data, card_summary_en, card_summary_ko,
          card_keywords, card_risk_score, card_thumbnail_url,
          tracked_projects!inner(id, name, slug, symbol)
        `)
        .eq('report_type', 'forensic')
        .in('status', ['published', 'coming_soon'])
        .in('card_qa_status', ['approved', 'pending'])
        .not('card_data', 'is', null)
        .order('published_at', { ascending: false })
        .limit(3),
    ])
    featuredProducts = productsRes.data || []
    categories = categoriesRes.data || []
    trackedProjects = projectsRes.data || []

    forensicReports = (forensicRes.data || []).filter(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (r: any) => r.tracked_projects !== null && r.card_data !== null
    )
  } catch (e) {
    console.error('Failed to fetch data:', e)
  }

  return (
    <div>
      {/* ★ Forensic Report Slide Thumbnails — TOP of page (sync render, no Suspense) */}
      {forensicReports.length > 0 && (
        <ForensicSlideCards reports={forensicReports} locale={locale} />
      )}

      {/* Tracked Projects Scores */}
      {trackedProjects.length > 0 && (
        <section className="max-w-6xl mx-auto px-6 py-20">
          <div className="flex justify-between items-center mb-10">
            <div>
              <h2 className="text-3xl font-bold text-white">{t('home.maturityScoreTitle')}</h2>
              <p className="text-gray-500 mt-2">
                {t('home.maturityScoreSubtitle')}
              </p>
            </div>
            <Link href={`/${locale}/score`} className="text-indigo-400 hover:text-indigo-300 transition-colors">
              {t('home.viewAll')} →
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
              {t('home.viewAllProjects')} →
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
            {t('home.browseAllReports')} →
          </Link>
        </div>
      </section>

      {/* About — 360° Project Intelligence (moved below content) */}
      <section className="relative overflow-hidden bg-gradient-to-br from-gray-950 via-indigo-950 to-gray-950 py-20 px-6">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative max-w-5xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-indigo-400 bg-clip-text text-transparent mb-6">
            {t('home.heroTitle')}
          </h2>
          <p className="text-lg text-gray-400 max-w-3xl mx-auto mb-8">
            {t('home.heroSubtitle')}
          </p>
          <div className="flex gap-4 justify-center flex-wrap mb-12">
            <Link
              href={`/${locale}/score`}
              className="px-8 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40"
            >
              {t('home.lookupScores')}
            </Link>
            <Link
              href={`/${locale}/subscribe`}
              className="px-8 py-3.5 bg-white/5 hover:bg-white/10 text-white font-semibold rounded-xl border border-white/10 transition-all"
            >
              {t('home.freeNewsletter')}
            </Link>
          </div>

          {/* 3 Report Types */}
          <div className="relative max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: '📊',
                type: t('home.econType'),
                title: t('home.econTitle'),
                desc: t('home.econDesc'),
                price: '$49',
                color: 'from-blue-500/10 to-blue-600/5 border-blue-500/20',
              },
              {
                icon: '📈',
                type: t('home.matType'),
                title: t('home.matTitle'),
                desc: t('home.matDesc'),
                price: '$39',
                color: 'from-green-500/10 to-green-600/5 border-green-500/20',
              },
              {
                icon: '🔍',
                type: t('home.forType'),
                title: t('home.forTitle'),
                desc: t('home.forDesc'),
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
        </div>
      </section>

      {/* Categories */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold mb-10">{t('home.researchDomains')}</h2>
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
            {t('home.newsletterTitle')}
          </h3>
          <p className="text-gray-400 mb-6">
            {t('home.newsletterSubtitle')}
          </p>
          <div className="flex justify-center gap-4 flex-wrap">
            <Link
              href={`/${locale}/subscribe`}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/25"
            >
              {t('home.subscribeFree')} →
            </Link>
          </div>
          <div className="flex justify-center gap-8 mt-6 text-sm text-gray-500">
            <span>📊 {t('home.weeklyPulse')}</span>
            <span>🔍 {t('home.deepDive')}</span>
            <span>🚨 {t('home.forensicAlerts')}</span>
          </div>
        </div>
      </section>

      {/* Crypto Payment Banner */}
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <div className="rounded-2xl bg-gradient-to-r from-green-500/5 to-emerald-500/5 border border-green-500/10 p-8 text-center">
          <h3 className="text-xl font-bold mb-3">{t('home.cryptoPayments')}</h3>
          <p className="text-gray-400 text-sm mb-4">{t('home.cryptoPaymentDesc')}</p>
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
