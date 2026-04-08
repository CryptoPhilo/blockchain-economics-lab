import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { type Locale } from '@/lib/types'
import ProductCard from '@/components/ProductCard'
import ProductFilter from '@/components/ProductFilter'

interface Props {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ type?: string; category?: string }>
}

export default async function ProductsPage({ params, searchParams }: Props) {
  const { locale } = await params
  const { type, category } = await searchParams
  const supabase = await createServerSupabaseClient()
  const t = await getTranslations('products')

  let query = supabase
    .from('products')
    .select('*, category:categories(*)')
    .eq('status', 'published')
    .order('featured', { ascending: false })
    .order('published_at', { ascending: false })

  if (type) query = query.eq('type', type)
  if (category) query = query.eq('category.slug', category)

  const { data: products } = await query
  const { data: categories } = await supabase.from('categories').select('*').order('sort_order')

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <h1 className="text-4xl font-bold mb-2">{t('title')}</h1>
      <p className="text-gray-400 mb-10">Browse our research reports, subscription plans, and bundles.</p>

      <ProductFilter currentType={type} currentCategory={category} categories={categories || []} locale={locale as Locale} />

      {products && products.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-8">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} locale={locale as Locale} />
          ))}
        </div>
      ) : (
        <div className="text-center py-20 text-gray-500">{t('noProducts')}</div>
      )}
    </div>
  )
}
