'use client'

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { getLocalizedField, formatPrice, type Product, type Locale } from '@/lib/types'

interface Props {
  product: Product
  locale: Locale
}

export default function ProductCard({ product, locale }: Props) {
  const t = useTranslations('products')
  const title = getLocalizedField(product, 'title', locale)
  const description = getLocalizedField(product, 'description', locale)

  const typeConfig: Record<string, { label: string; color: string; icon: string }> = {
    single_report: { label: t('singleReports'), color: 'bg-blue-500/20 text-blue-400', icon: '📄' },
    subscription: { label: t('subscriptions'), color: 'bg-green-500/20 text-green-400', icon: '🔄' },
    bundle: { label: t('bundles'), color: 'bg-purple-500/20 text-purple-400', icon: '📦' },
    project_subscription: { label: t('subscriptions'), color: 'bg-emerald-500/20 text-emerald-400', icon: '🔔' },
  }

  const config = typeConfig[product.type] || typeConfig.single_report

  return (
    <Link
      href={`/${locale}/products/${product.slug}`}
      className="group flex flex-col p-6 rounded-2xl bg-white/[0.03] border border-white/5 hover:border-indigo-500/30 hover:bg-indigo-500/[0.03] transition-all duration-300"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${config.color}`}>
          {config.icon} {config.label}
        </span>
        {product.featured && (
          <span className="px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-400">⭐ {t('featured')}</span>
        )}
      </div>

      {/* Category */}
      {product.category && (
        <p className="text-xs text-gray-600 mb-2">
          {(product.category as any).icon} {getLocalizedField(product.category as any, 'name', locale)}
        </p>
      )}

      {/* Title */}
      <h3 className="text-lg font-semibold text-white group-hover:text-indigo-400 transition-colors line-clamp-2 mb-2">
        {title}
      </h3>

      {/* Description */}
      <p className="text-sm text-gray-500 line-clamp-3 mb-4 flex-1">
        {description}
      </p>

      {/* Tags */}
      {product.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {product.tags.slice(0, 3).map((tag) => (
            <span key={tag} className="px-2 py-0.5 bg-white/5 rounded text-xs text-gray-500">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Price */}
      <div className="mt-auto pt-4 border-t border-white/5 flex items-center justify-between">
        <span className="text-xl font-bold text-indigo-400">
          {formatPrice(product.price_usd_cents)}
        </span>
        {product.type === 'subscription' && (
          <span className="text-sm text-gray-500">
            {product.subscription_interval === 'monthly' ? t('perMonth') : t('perYear')}
          </span>
        )}
        {product.type === 'single_report' && (
          <span className="text-sm text-indigo-400 group-hover:translate-x-1 transition-transform">→</span>
        )}
      </div>
    </Link>
  )
}
