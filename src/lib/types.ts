export type ProductType = 'single_report' | 'subscription' | 'bundle' | 'project_subscription'
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
  report_type?: 'econ' | 'maturity' | 'forensic'
  report_version?: number
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

export interface BundleItem {
  id: string
  bundle_id: string
  product_id: string
  sort_order: number
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

// ============================================================
// Tracked Projects & Report Production Types
// ============================================================

export type ProjectStatus = 'discovered' | 'under_review' | 'active' | 'monitoring_only' | 'suspended' | 'archived'
export type ReportType = 'econ' | 'maturity' | 'forensic'
export type ReportStatus = 'assigned' | 'in_progress' | 'in_review' | 'approved' | 'published' | 'coming_soon' | 'cancelled'
export type ProjectSubTier = 'single' | 'triple' | 'five' | 'all'

export interface TrackedProject {
  id: string
  name: string
  slug: string
  symbol: string
  chain?: string
  category?: string
  status: ProjectStatus
  discovered_at: string
  discovered_by?: string
  discovery_source?: string
  market_cap_usd?: number
  tvl_usd?: number
  coingecko_id?: string
  website_url?: string
  last_econ_report_at?: string
  last_maturity_report_at?: string
  last_forensic_report_at?: string
  next_econ_due_at?: string
  next_maturity_due_at?: string
  forensic_monitoring: boolean
  maturity_score?: number
  maturity_stage?: string
  primary_analyst_id?: string
  created_at: string
}

export type SupportedLanguage = 'en' | 'ko' | 'fr' | 'es' | 'de' | 'ja' | 'zh'
export type TranslationStatus = Record<SupportedLanguage, 'pending' | 'in_progress' | 'completed'>

export interface GDriveUrlEntry {
  url: string
  download_url?: string
}

export interface ReportCardData {
  report_type?: 'for' | 'econ' | 'mat'
  risk_level?: string
  risk_score?: number
  rating?: string
  maturity_score?: number
  maturity_stage?: string
  keywords?: string[]
  keywords_en?: string[]
  keywords_ko?: string[]
  keywords_by_lang?: Record<string, string[]>
  summary?: string
  summary_en?: string
  summary_ko?: string
  summary_by_lang?: Record<string, string>
  price_change_24h?: number
  change_24h?: number
  direction?: 'up' | 'down'
  generated_at?: string
}

export interface ProjectReport {
  id: string
  project_id: string
  product_id?: string
  report_type: ReportType
  version: number
  status: ReportStatus
  language: SupportedLanguage
  assigned_to?: string
  assigned_at: string
  started_at?: string
  review_at?: string
  approved_at?: string
  published_at?: string
  created_at: string
  trigger_reason?: string
  risk_level?: string
  is_free?: boolean
  card_risk_score?: number
  card_keywords?: string[]
  card_summary_en?: string
  card_summary_ko?: string
  card_summary_fr?: string
  card_summary_es?: string
  card_summary_de?: string
  card_summary_ja?: string
  card_summary_zh?: string
  card_data?: ReportCardData | null
  file_url?: string
  file_urls_by_lang?: Record<SupportedLanguage, string>
  gdrive_url?: string
  gdrive_download_url?: string
  gdrive_urls_by_lang?: Record<string, GDriveUrlEntry | string>
  page_count?: number
  task_id?: string
  title_en?: string
  title_ko?: string
  title_fr?: string
  title_es?: string
  title_de?: string
  title_ja?: string
  title_zh?: string
  translation_status?: TranslationStatus
  project?: TrackedProject
  product?: Product
}

export interface ForensicMonitoringLog {
  id: string
  project_id: string
  check_date: string
  price_change_24h?: number
  volume_ratio?: number
  whale_movement_pct?: number
  exchange_netflow_pct?: number
  insider_activity?: string
  total_flags: number
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  flag_details?: Record<string, any>
  action: string
  analyst_id?: string
  notes?: string
  project?: TrackedProject
}

export interface ProjectSubscription {
  id: string
  user_id: string
  tier: ProjectSubTier
  status: SubscriptionStatus
  payment_method: PaymentMethod
  price_usd_cents: number
  interval: 'monthly' | 'yearly'
  current_period_start?: string
  current_period_end?: string
  crypto_wallet_address?: string
  cancelled_at?: string
  created_at: string
  items?: ProjectSubscriptionItem[]
}

export interface ProjectSubscriptionItem {
  id: string
  project_subscription_id: string
  project_id: string
  added_at: string
  project?: TrackedProject
}

// ============================================================
// Trading Signal Types
// ============================================================

export type TradingSignalDirection = 'long' | 'short' | 'hold'
export type TradingSignalReviewStatus = 'pending_review' | 'approved' | 'rejected'
export type TradingSignalReviewAction = 'approve' | 'reject' | 'manual_override'

export interface TradingSignalRun {
  id: string
  source: string
  model_version?: string
  features_version?: string
  method?: string
  generated_at: string
  source_window_start?: string
  source_window_end?: string
  input_uri?: string
  metadata?: Record<string, unknown>
  created_at: string
}

export interface TradingSignal {
  id: string
  run_id: string
  project_id: string
  signal_date: string
  horizon_days: number
  direction: TradingSignalDirection
  confidence?: number
  predicted_return_1d?: number
  historical_direction_accuracy?: number
  last_spot_close?: number
  predicted_spot_close_1d?: number
  review_status: TradingSignalReviewStatus
  reviewed_at?: string
  reviewed_by?: string
  approved_at?: string
  rejected_at?: string
  created_at: string
  project?: TrackedProject
  run?: TradingSignalRun
}

export interface TradingSignalReview {
  id: string
  signal_id: string
  action: TradingSignalReviewAction
  actor_id?: string
  note?: string
  metadata?: Record<string, unknown>
  created_at: string
}

export interface CreateTradingSignalRunInput {
  source?: string
  modelVersion?: string
  featuresVersion?: string
  method?: string
  generatedAt: string
  sourceWindowStart?: string
  sourceWindowEnd?: string
  inputUri?: string
  metadata?: Record<string, unknown>
}

export interface CreateTradingSignalInput {
  runId: string
  projectId: string
  signalDate: string
  horizonDays?: number
  direction: TradingSignalDirection
  confidence?: number
  predictedReturn1d?: number
  historicalDirectionAccuracy?: number
  lastSpotClose?: number
  predictedSpotClose1d?: number
}

export interface CreateTradingSignalReviewInput {
  signalId: string
  action: TradingSignalReviewAction
  actorId?: string
  note?: string
  metadata?: Record<string, unknown>
}

// ============================================================
// Referral Tracking Types
// ============================================================

export type ExchangeName = 'binance' | 'bybit' | 'okx'
export type ReferralStatus = 'pending' | 'active' | 'suspended'
export type ReferralSource = 'report' | 'newsletter' | 'web' | 'telegram' | 'twitter' | 'score_lookup'
export type ReferralContentType = 'report' | 'newsletter' | 'trade_thesis' | 'forensic_alert' | 'score_page'
export type EarningsStatus = 'pending' | 'confirmed' | 'paid'

export interface ExchangeReferral {
  id: string
  exchange: ExchangeName
  referral_code: string
  referral_url: string
  revshare_pct?: number
  status: ReferralStatus
  applied_at?: string
  approved_at?: string
  created_at: string
}

export interface ReferralClick {
  id: string
  user_id?: string
  exchange: ExchangeName
  source: ReferralSource
  content_id?: string
  content_type?: ReferralContentType
  ip_country?: string
  geo_blocked: boolean
  clicked_at: string
}

export interface ReferralEarnings {
  id: string
  exchange: ExchangeName
  period_start: string
  period_end: string
  referred_users: number
  active_traders: number
  total_volume_usd: number
  commission_usd: number
  status: EarningsStatus
  created_at: string
}

// ============================================================
// Newsletter & Subscriber Types
// ============================================================

export type NewsletterType = 'market_pulse' | 'deep_dive' | 'forensic_alert' | 'trade_thesis'
export type NewsletterStatus = 'draft' | 'review' | 'approved' | 'sending' | 'sent'
export type NewsletterEventType = 'delivered' | 'opened' | 'clicked' | 'bounced' | 'unsubscribed'
export type SubscriberSource = 'website' | 'report_download' | 'referral' | 'score_lookup' | 'telegram' | 'twitter'
export type ThreatLevel = 'clear' | 'watch' | 'caution' | 'warning' | 'critical'

export interface Subscriber {
  id: string
  email: string
  name?: string
  locale: Locale
  source?: SubscriberSource
  opted_in: boolean
  opt_in_token?: string
  opt_in_sent_at?: string
  confirmed_at?: string
  unsubscribed: boolean
  unsubscribed_at?: string
  ip_country?: string
  created_at: string
}

export interface Newsletter {
  id: string
  type: NewsletterType
  title_en: string
  title_ko?: string
  content_md: string
  content_html?: string
  status: NewsletterStatus
  scheduled_at?: string
  sent_at?: string
  total_recipients: number
  created_at: string
}

export interface NewsletterEvent {
  id: string
  newsletter_id: string
  subscriber_id: string
  event_type: NewsletterEventType
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata?: Record<string, any>
  occurred_at: string
}

// ============================================================
// BCE Maturity Score Types
// ============================================================

export interface BCEMaturityScores {
  technology: number
  business: number
  tokenomics: number
  governance: number
  community: number
  compliance: number
  narrative: number
}

export const BCE_SCORE_WEIGHTS: Record<keyof BCEMaturityScores, number> = {
  technology: 0.20,
  business: 0.20,
  tokenomics: 0.15,
  governance: 0.10,
  community: 0.10,
  compliance: 0.10,
  narrative: 0.15,
}

export function calculateBCEScore(scores: BCEMaturityScores): number {
  return Object.entries(BCE_SCORE_WEIGHTS).reduce((total, [key, weight]) => {
    return total + (scores[key as keyof BCEMaturityScores] || 0) * weight
  }, 0)
}

// Helper: get localized field from product/category
// eslint-disable-next-line @typescript-eslint/no-explicit-any
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
