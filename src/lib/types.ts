export type ProductType = 'single_report' | 'subscription' | 'bundle'
export type ProductStatus = 'draft' | 'published' | 'archived'
export type PaymentMethod = 'stripe' | 'crypto_btc' | 'crypto_eth' | 'crypto_usdt' | 'crypto_usdc'
export type OrderStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'refunded' | 'expired'
export type SubscriptionStatus = 'active' | 'past_due' | 'cancelled' | 'expired' | 'trialing'
export type Locale = 'en' | 'ko' | 'fr' | 'es' | 'de' | 'ja' | 'zh'

export interface Category {
  id: string
  slug: string
  name_en: string
  name_ko?: string
  name_fr?: string
  name_es?: string
  name_de?: string
  name_ja?: string
  name_zh?: string
  description_en?: string
  description_ko?: string
  icon?: string
  sort_order: number
}

export interface Product {
  id: string
  type: ProductType
  status: ProductStatus
  slug: string
  title_en: string
  title_ko?: string
  title_fr?: string
  title_es?: string
  title_de?: string
  title_ja?: string
  title_zh?: string
  description_en?: string
  description_ko?: string
  description_fr?: string
  description_es?: string
  description_de?: string
  description_ja?: string
  description_zh?: string
  price_usd_cents: number
  subscription_interval?: 'monthly' | 'yearly'
  category_id?: string
  category?: Category
  cover_image_url?: string
  preview_url?: string
  file_url?: string
  tags: string[]
  featured: boolean
  author_agent_id?: string
  published_at?: string
  created_at: string
}

export interface Order {
  id: string
  user_id: string
  status: OrderStatus
  payment_method: PaymentMethod
  subtotal_cents: number
  discount_cents: number
  total_cents: number
  crypto_amount?: string
  crypto_currency?: string
  crypto_tx_hash?: string
  stripe_payment_intent_id?: string
  paid_at?: string
  created_at: string
  items?: OrderItem[]
}

export interface OrderItem {
  id: string
  order_id: string
  product_id: string
  quantity: number
  unit_price_cents: number
  product?: Product
}

export interface Subscription {
  id: string
  user_id: string
  product_id: string
  status: SubscriptionStatus
  payment_method: PaymentMethod
  current_period_start?: string
  current_period_end?: string
  product?: Product
}

export interface UserLibraryItem {
  id: string
  user_id: string
  product_id: string
  order_id?: string
  subscription_id?: string
  access_granted_at: string
  access_expires_at?: string
  download_count: number
  product?: Product
}

// Helper: get localized field from product/category
export function getLocalizedField<T extends Record<string, any>>(
  item: T,
  field: string,
  locale: Locale
): string {
  const localizedKey = `${field}_${locale}`
  return (item[localizedKey] || item[`${field}_en`] || '') as string
}

// Format price from cents to display string
export function formatPrice(cents: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}
