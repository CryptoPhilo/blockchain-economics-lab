import { getTranslations } from 'next-intl/server'
import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocalizedField, type Locale } from '@/lib/types'
import DisclaimerBanner from '@/components/DisclaimerBanner'
import LatestReportShowcase from '@/components/LatestReportShowcase'

const SHOWCASE_PRODUCT_BACKFILL_LIMIT = 24
const SHOWCASE_REPORT_BACKFILL_LIMIT = 120

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t = await getTranslations()

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let categories: any[] = []
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let latestReportCoverProducts: any[] = []
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let latestReportCovers: any[] = []

  try {
    const supabase = await createServerSupabaseClient()
    const [categoriesRes, latestCoverProductsRes, latestReportCoversRes] = await Promise.all([
      supabase
        .from('categories')
        .select('*')
        .order('sort_order'),
      supabase
        .from('products')
        .select('*, category:categories(*)')
        .eq('status', 'published')
        .eq('type', 'single_report')
        .in('report_type', ['econ', 'maturity', 'forensic'])
        .not('cover_image_url', 'is', null)
        .order('published_at', { ascending: false, nullsFirst: false })
        // Keep a wider backfill pool so the first-screen showcase can stay populated
        // when the newest reports lack locale-ready covers or slides.
        .limit(SHOWCASE_PRODUCT_BACKFILL_LIMIT),
      supabase
        .from('project_reports')
        .select(`
          *,
          tracked_projects(id, name, slug, symbol, chain, category),
          product:products(
            id,
            slug,
            title_en,
            title_ko,
            title_fr,
            title_es,
            title_de,
            title_ja,
            title_zh,
            cover_image_url,
            published_at
          )
        `)
        .eq('status', 'published')
        .in('report_type', ['econ', 'maturity', 'forensic'])
        .order('published_at', { ascending: false, nullsFirst: false })
        .order('updated_at', { ascending: false, nullsFirst: false })
        .limit(SHOWCASE_REPORT_BACKFILL_LIMIT),
    ])
    categories = categoriesRes.data || []
    latestReportCoverProducts = latestCoverProductsRes.data || []
    latestReportCovers = latestReportCoversRes.data || []
  } catch (e) {
    console.error('Failed to fetch data:', e)
  }

  return (
    <div>
      {/* Latest report covers */}
      {(latestReportCoverProducts.length > 0 || latestReportCovers.length > 0) && (
        <LatestReportShowcase products={latestReportCoverProducts} reports={latestReportCovers} locale={locale} />
      )}

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
          {/* 3 Report Types */}
          <div className="relative max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: '📊',
                type: t('home.econType'),
                title: t('home.econTitle'),
                desc: t('home.econDesc'),
                color: 'from-blue-500/10 to-blue-600/5 border-blue-500/20',
              },
              {
                icon: '📈',
                type: t('home.matType'),
                title: t('home.matTitle'),
                desc: t('home.matDesc'),
                color: 'from-green-500/10 to-green-600/5 border-green-500/20',
              },
              {
                icon: '🔍',
                type: t('home.forType'),
                title: t('home.forTitle'),
                desc: t('home.forDesc'),
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

      {/* Disclaimer */}
      <section className="max-w-6xl mx-auto px-6 pb-10">
        <DisclaimerBanner />
      </section>
    </div>
  )
}
