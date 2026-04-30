import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocalizedField, type Locale } from '@/lib/types'
import { notFound } from 'next/navigation'
import Link from 'next/link'

interface Props {
  params: Promise<{ locale: string; slug: string }>
}

const REPORT_TYPE_CONFIG = {
  econ: { color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', label: 'ECON', icon: '📊', tooltip: 'Economic Analysis' },
  maturity: { color: 'bg-green-500/20 text-green-400 border-green-500/30', label: 'MAT', icon: '📈', tooltip: 'Maturity Analysis' },
  forensic: { color: 'bg-red-500/20 text-red-400 border-red-500/30', label: 'FOR', icon: '🔍', tooltip: 'Forensic Analysis' },
} as const

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export default async function ProductDetailPage({ params }: Props) {
  const { locale, slug } = await params
  const supabase = await createServerSupabaseClient()
  const t = await getTranslations()

  const { data: product } = await supabase
    .from('products')
    .select('*, category:categories(*)')
    .eq('slug', slug)
    .eq('status', 'published')
    .single()

  if (!product) notFound()

  // If bundle, fetch items
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let bundleItems: any[] = []
  if (product.type === 'bundle') {
    const { data } = await supabase
      .from('bundle_items')
      .select('*, product:products(*)')
      .eq('bundle_id', product.id)
      .order('sort_order')
    bundleItems = data || []
  }

  const title = getLocalizedField(product, 'title', locale as Locale)
  const description = getLocalizedField(product, 'description', locale as Locale)
  const reportType = product.report_type as keyof typeof REPORT_TYPE_CONFIG | null
  const reportTypeConfig = reportType ? REPORT_TYPE_CONFIG[reportType] : null
  const version = product.report_version as number | null
  const newsletterCopy = locale === 'ko'
    ? {
        title: '무료 뉴스레터로 업데이트 받기',
        body: '새 리포트 공개와 핵심 프로젝트 인사이트를 이메일로 받아보세요.',
        cta: '무료 뉴스레터 구독',
        note: '리포트 접근 안내는 뉴스레터를 통해 업데이트됩니다.',
      }
    : {
        title: 'Get updates through the free newsletter',
        body: 'Receive new report releases and concise project intelligence by email.',
        cta: 'Subscribe free',
        note: 'Report access updates are shared through the newsletter.',
      }

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <Link href={`/${locale}/products`} className="text-indigo-400 hover:text-indigo-300 text-sm mb-6 inline-block">
        ← {t('common.back')}
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        {/* Main Content */}
        <div className="lg:col-span-2">
          <div className="flex items-center gap-3 mb-4">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              product.type === 'single_report' ? 'bg-blue-500/20 text-blue-400' :
              product.type === 'subscription' ? 'bg-green-500/20 text-green-400' :
              'bg-purple-500/20 text-purple-400'
            }`}>
              {product.type === 'single_report' ? t('products.singleReports') :
               product.type === 'subscription' ? t('products.subscriptions') :
               t('products.bundles')}
            </span>
            {reportTypeConfig && (
              <span
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase ${reportTypeConfig.color}`}
                title={reportTypeConfig.tooltip}
              >
                {reportTypeConfig.icon} {reportTypeConfig.label}
              </span>
            )}
            {product.category && (
              <span className="text-sm text-gray-500">{product.category.icon} {getLocalizedField(product.category, 'name', locale as Locale)}</span>
            )}
          </div>

          <h1 className="text-3xl font-bold mb-2">{title}</h1>

          {/* Publication date and version info */}
          <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500 mb-4">
            {product.published_at && (
              <span>{locale === 'ko' ? '발행일' : 'Published'}: {formatDate(product.published_at)}</span>
            )}
            {version && (
              <>
                <span className="text-gray-700">·</span>
                <span className="inline-flex items-center gap-1.5">
                  v{version}
                  {version > 1 && (
                    <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 text-[11px] font-medium">
                      {locale === 'ko' ? '업데이트됨' : 'Updated'}
                    </span>
                  )}
                </span>
              </>
            )}
            {!product.published_at && product.created_at && (
              <span>{locale === 'ko' ? '등록일' : 'Listed'}: {formatDate(product.created_at)}</span>
            )}
          </div>

          <p className="text-gray-400 text-lg leading-relaxed mb-8">{description}</p>

          {product.tags?.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-8">
              { }
              {product.tags.map((tag: string) => (
                <span key={tag} className="px-3 py-1 bg-white/5 rounded-full text-sm text-gray-400">#{tag}</span>
              ))}
            </div>
          )}

          {/* Bundle Contents */}
          {bundleItems.length > 0 && (
            <div className="mt-8">
              <h3 className="text-xl font-semibold mb-4">{t('products.includes')}</h3>
              <div className="space-y-3">
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                {bundleItems.map((item: any) => (
                  <div key={item.id} className="flex items-center gap-3 p-4 rounded-lg bg-white/5 border border-white/5">
                    <span className="text-green-400">✓</span>
                    <span>{getLocalizedField(item.product, 'title', locale as Locale)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Newsletter Card */}
        <div className="lg:col-span-1">
          <div className="sticky top-24 p-6 rounded-2xl bg-white/5 border border-white/10">
            <h2 className="text-xl font-bold text-white mb-3">{newsletterCopy.title}</h2>
            <p className="text-sm text-gray-400 leading-6 mb-5">{newsletterCopy.body}</p>
            <Link
              href={`/${locale}#newsletter`}
              className="inline-flex w-full items-center justify-center rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-indigo-500"
            >
              {newsletterCopy.cta}
            </Link>
            <p className="mt-4 text-xs text-gray-500 text-center">{newsletterCopy.note}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
