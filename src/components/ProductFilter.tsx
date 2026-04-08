'use client'

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { getLocalizedField, type Category, type Locale } from '@/lib/types'

interface Props {
  currentType?: string
  currentCategory?: string
  categories: Category[]
  locale: Locale
}

export default function ProductFilter({ currentType, currentCategory, categories, locale }: Props) {
  const t = useTranslations('products')

  const types = [
    { value: undefined, label: t('filterAll') },
    { value: 'single_report', label: t('singleReports') },
    { value: 'subscription', label: t('subscriptions') },
    { value: 'bundle', label: t('bundles') },
  ]

  function buildUrl(type?: string, category?: string) {
    const params = new URLSearchParams()
    if (type) params.set('type', type)
    if (category) params.set('category', category)
    const qs = params.toString()
    return `/${locale}/products${qs ? '?' + qs : ''}`
  }

  return (
    <div className="space-y-4">
      {/* Type Filter */}
      <div className="flex flex-wrap gap-2">
        {types.map((type) => (
          <Link
            key={type.value || 'all'}
            href={buildUrl(type.value, currentCategory)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              currentType === type.value
                ? 'bg-indigo-600 text-white'
                : !currentType && !type.value
                ? 'bg-indigo-600 text-white'
                : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
            }`}
          >
            {type.label}
          </Link>
        ))}
      </div>

      {/* Category Filter */}
      <div className="flex flex-wrap gap-2">
        <Link
          href={buildUrl(currentType)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            !currentCategory ? 'bg-white/10 text-white' : 'bg-white/5 text-gray-500 hover:text-gray-300'
          }`}
        >
          All Categories
        </Link>
        {categories.map((cat) => (
          <Link
            key={cat.id}
            href={buildUrl(currentType, cat.slug)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              currentCategory === cat.slug ? 'bg-white/10 text-white' : 'bg-white/5 text-gray-500 hover:text-gray-300'
            }`}
          >
            {cat.icon} {getLocalizedField(cat, 'name', locale)}
          </Link>
        ))}
      </div>
    </div>
  )
}
