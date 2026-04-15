import { getTranslations } from 'next-intl/server'
import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocalizedField, type Locale } from '@/lib/types'
import ProductCard from '@/components/ProductCard'
import DisclaimerBanner from '@/components/DisclaimerBanner'
import SubscribeForm from '@/components/SubscribeForm'
import ForensicSlideCards from '@/components/ForensicSlideCards'

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t = await getTranslations()

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let featuredProducts: any[] = []
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let categories: any[] = []
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let forensicReports: any[] = []

  try {
    const supabase = await createServerSupabaseClient()
    const [productsRes, categoriesRes, forensicRes] = await Promise.all([
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
        .from('project_reports')
        .select('*, tracked_projects!inner(id, name, slug, symbol, chain, category)')
        .eq('report_type', 'forensic')
        .eq('status', 'published')
        .not('card_data', 'is', null)
        .order('published_at', { ascending: false })
        .limit(8),
    ])
    featuredProducts = productsRes.data || []
    categories = categoriesRes.data || []
    forensicReports = forensicRes.data || []
  } catch (e) {
    console.error('Failed to fetch data:', e)
  }

  return (
    <div>

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
          <SubscribeForm
            locale={locale}
            source="homepage"
            className="mb-12"
            translations={{
              placeholder: t('subscribe.emailPlaceholder'),
              cta: t('home.freeNewsletter'),
              success: t('subscribe.checkEmail'),
            }}
          />

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

      {/* Forensic Slide Cards */}
      <ForensicSlideCards reports={forensicReports} locale={locale} />

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
          <SubscribeForm
            locale={locale}
            source="newsletter"
            translations={{
              placeholder: t('subscribe.emailPlaceholder'),
              cta: t('home.subscribeFree'),
              success: t('subscribe.checkEmail'),
            }}
          />
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
