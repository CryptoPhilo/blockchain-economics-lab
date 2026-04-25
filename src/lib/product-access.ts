import type { Product } from '@/lib/types'

const SIGNAL_PRODUCT_KEYWORDS = [
  'signal',
  'signals',
  'beta',
  'starter',
  'basic',
  'pro',
  'premium',
  '시그널',
]

function tokenize(value: string | null | undefined) {
  if (!value) return []

  return value
    .toLowerCase()
    .split(/[^a-z0-9가-힣]+/)
    .filter(Boolean)
}

export function areSignalProductsPubliclyEnabled() {
  return process.env.SIGNAL_PRODUCTS_PUBLIC_ENABLED === 'true'
}

export function isSignalProduct(product: Pick<Product, 'slug' | 'title_en' | 'title_ko' | 'description_en' | 'description_ko' | 'tags'>) {
  const tokens = new Set([
    ...tokenize(product.slug),
    ...tokenize(product.title_en),
    ...tokenize(product.title_ko),
    ...tokenize(product.description_en),
    ...tokenize(product.description_ko),
    ...(product.tags || []).flatMap((tag) => tokenize(tag)),
  ])

  return SIGNAL_PRODUCT_KEYWORDS.some((keyword) => tokens.has(keyword))
}

export function isProductPubliclyAvailable(
  product: Pick<Product, 'status' | 'slug' | 'title_en' | 'title_ko' | 'description_en' | 'description_ko' | 'tags'>
) {
  if (product.status !== 'published') {
    return false
  }

  if (isSignalProduct(product) && !areSignalProductsPubliclyEnabled()) {
    return false
  }

  return true
}

export function filterPublicProducts<T extends Pick<Product, 'status' | 'slug' | 'title_en' | 'title_ko' | 'description_en' | 'description_ko' | 'tags'>>(products: T[]) {
  return products.filter((product) => isProductPubliclyAvailable(product))
}
