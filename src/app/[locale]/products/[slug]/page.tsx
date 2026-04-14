import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocalizedField, formatPrice, type Locale } from '@/lib/types'
import { notFound } from 'next/navigation'
import Link from 'next/link'
import CheckoutButton from '@/components/CheckoutButton'

interface Props {
  params: Promise<{ locale: string; slug: string }>
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
            {product.category && (
              <span className="text-sm text-gray-500">{product.category.icon} {getLocalizedField(product.category, 'name', locale as Locale)}</span>
            )}
          </div>

          <h1 className="text-3xl font-bold mb-4">{title}</h1>
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
                    <span className="ml-auto text-sm text-gray-500">{formatPrice(item.product.price_usd_cents)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Purchase Card */}
        <div className="lg:col-span-1">
          <div className="sticky top-24 p-6 rounded-2xl bg-white/5 border border-white/10">
            <div className="text-3xl font-bold text-indigo-400 mb-1">
              {formatPrice(product.price_usd_cents)}
              {product.type === 'subscription' && (
                <span className="text-base font-normal text-gray-500">
                  {product.subscription_interval === 'monthly' ? t('products.perMonth') : t('products.perYear')}
                </span>
              )}
            </div>

            {product.type === 'bundle' && (
              <p className="text-sm text-green-400 mb-4">🎉 {t('products.savePercent', { percent: '25' })}</p>
            )}

            <CheckoutButton product={product} locale={locale} />

            <div className="mt-6 pt-6 border-t border-white/10">
              <p className="text-xs text-gray-500 text-center">Secure crypto payment — BTC, ETH, USDT, USDC</p>
              <div className="flex justify-center gap-3 mt-3 text-lg">
                <span>₿</span><span>Ξ</span><span>₮</span><span>💲</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
