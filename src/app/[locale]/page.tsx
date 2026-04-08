import { getTranslations } from 'next-intl/server'
import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocalizedField, type Locale } from '@/lib/types'
import ProductCard from '@/components/ProductCard'

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t = await getTranslations()

  let featuredProducts: any[] = []
  let categories: any[] = []

  try {
    const supabase = await createServerSupabaseClient()
    const [productsRes, categoriesRes] = await Promise.all([
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
    ])
    featuredProducts = productsRes.data || []
    categories = categoriesRes.data || []
  } catch (e) {
    console.error('Failed to fetch data:', e)
  }

  return (
    <div>
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-gray-950 via-indigo-950 to-gray-950 py-24 px-6">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm mb-8">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
            AI-Powered Research
          </div>
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-indigo-400 bg-clip-text text-transparent mb-6">
            {t('hero.title')}
          </h1>
          <p className="text-xl text-gray-400 max-w-3xl mx-auto mb-10">
            {t('hero.subtitle')}
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              href={`/${locale}/products`}
              className="px-8 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40"
            >
              {t('hero.cta')}
            </Link>
            <Link
              href={`/${locale}/products?type=subscription`}
              className="px-8 py-3.5 bg-white/5 hover:bg-white/10 text-white font-semibold rounded-xl border border-white/10 transition-all"
            >
              {t('hero.ctaSecondary')}
            </Link>
          </div>
        </div>
        {/* Stats */}
        <div className="relative max-w-4xl mx-auto mt-20 grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { value: '120+', label: 'Reports Published' },
            { value: '$2.4B', label: 'TVL Analyzed' },
            { value: '12', label: 'AI Research Agents' },
            { value: '15K+', label: 'Subscribers' },
          ].map((stat) => (
            <div key={stat.label} className="text-center p-4 rounded-xl bg-white/5 border border-white/5">
              <div className="text-2xl font-bold text-indigo-400">{stat.value}</div>
              <div className="text-sm text-gray-500 mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Categories */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold mb-10">{t('categories.onchain-analytics') ? 'Research Domains' : 'Research Domains'}</h2>
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
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <div className="flex justify-between items-center mb-10">
          <h2 className="text-3xl font-bold">{t('products.featured')}</h2>
          <Link href={`/${locale}/products`} className="text-indigo-400 hover:text-indigo-300 transition-colors">
            {t('common.viewAll')} →
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {featuredProducts?.map((product) => (
            <ProductCard key={product.id} product={product} locale={locale as Locale} />
          ))}
        </div>
      </section>

      {/* Payment Methods Banner */}
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <div className="rounded-2xl bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 p-10 text-center">
          <h3 className="text-2xl font-bold mb-4">Crypto-Native Payments</h3>
          <p className="text-gray-400 mb-6">Pay with cryptocurrency — BTC, ETH, USDT, USDC accepted</p>
          <div className="flex justify-center gap-6 text-3xl">
            <span title="Bitcoin">₿</span>
            <span title="Ethereum">Ξ</span>
            <span title="USDT">₮</span>
            <span title="USDC">💲</span>
          </div>
        </div>
      </section>
    </div>
  )
}
