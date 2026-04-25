import Link from 'next/link'
import { formatPrice, type Product, type Subscription } from '@/lib/types'
import type { DashboardBetaSignalSnapshot } from '@/lib/repositories'

interface DashboardBetaSignalsSectionProps {
  locale: string
  subscriptions: Subscription[]
  plans: Product[]
  signalSnapshot: DashboardBetaSignalSnapshot
}

type PlanStatus = 'active' | 'included' | 'locked'

const STARTER_KEYWORDS = ['starter', 'basic']
const PRO_KEYWORDS = ['pro', 'premium']

function normalizePlanTokens(product: Product | undefined) {
  if (!product) return []

  return [
    product.slug,
    product.title_en,
    product.title_ko,
    ...(product.tags || []),
  ]
    .filter((value): value is string => typeof value === 'string' && value.length > 0)
    .flatMap((value) =>
      value
        .toLowerCase()
        .split(/[^a-z0-9]+/)
        .filter(Boolean)
    )
}

function hasExplicitTierKeyword(product: Product | undefined, keywords: string[]) {
  const tokens = new Set(normalizePlanTokens(product))
  return keywords.some((keyword) => tokens.has(keyword))
}

function findExplicitTierPlan(plans: Product[], keywords: string[]) {
  const matches = plans.filter((plan) => hasExplicitTierKeyword(plan, keywords))

  if (matches.length !== 1) {
    return null
  }

  return matches[0]
}

export function resolveSignalPlans(plans: Product[]) {
  const subscriptionPlans = plans.filter((plan) => plan.type === 'subscription')
  const starter = findExplicitTierPlan(subscriptionPlans, STARTER_KEYWORDS)
  const pro = findExplicitTierPlan(subscriptionPlans, PRO_KEYWORDS)

  return { starter, pro }
}

export function resolveStatuses(subscriptions: Subscription[], starterPlan: Product | null, proPlan: Product | null) {
  const activeProductIds = new Set(
    subscriptions
      .map((subscription) => subscription.product_id || subscription.product?.id)
      .filter((productId): productId is string => Boolean(productId))
  )

  const hasPro = Boolean(proPlan && activeProductIds.has(proPlan.id))
  const hasStarter = hasPro || Boolean(starterPlan && activeProductIds.has(starterPlan.id))

  return {
    starter: hasPro ? 'included' : hasStarter ? 'active' : 'locked',
    pro: hasPro ? 'active' : 'locked',
  } satisfies { starter: PlanStatus; pro: PlanStatus }
}

function getStatusLabel(locale: string, status: PlanStatus) {
  const isKo = locale === 'ko'

  if (status === 'active') return isKo ? '활성' : 'Active'
  if (status === 'included') return isKo ? 'Pro에 포함' : 'Included in Pro'
  return isKo ? '잠김' : 'Locked'
}

function getStatusClasses(status: PlanStatus) {
  if (status === 'active') return 'bg-emerald-500/15 text-emerald-300 border border-emerald-400/20'
  if (status === 'included') return 'bg-sky-500/15 text-sky-300 border border-sky-400/20'
  return 'bg-white/8 text-gray-300 border border-white/10'
}

function renderPrice(locale: string, plan: Product | null) {
  if (!plan) {
    return locale === 'ko' ? '플랜 준비 중' : 'Plan coming soon'
  }

  const interval = plan.subscription_interval === 'yearly'
    ? (locale === 'ko' ? '/년' : '/year')
    : (locale === 'ko' ? '/월' : '/month')

  return `${formatPrice(plan.price_usd_cents)}${interval}`
}

function getPlanHref(locale: string, plan: Product | null) {
  if (!plan) return `/${locale}/products?type=subscription`
  return `/${locale}/products/${plan.slug}`
}

function formatDateTime(locale: string, value: string | null) {
  if (!value) return locale === 'ko' ? '업데이트 없음' : 'Unavailable'

  return new Date(value).toLocaleString(locale === 'ko' ? 'ko-KR' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatPercent(value: number | null) {
  if (value === null) return '—'
  return `${(value * 100).toFixed(2)}%`
}

export default function DashboardBetaSignalsSection({
  locale,
  subscriptions,
  plans,
  signalSnapshot,
}: DashboardBetaSignalsSectionProps) {
  const isKo = locale === 'ko'
  const { starter, pro } = resolveSignalPlans(plans)
  const statuses = resolveStatuses(subscriptions, starter, pro)
  const hasAccess = statuses.starter !== 'locked' || statuses.pro !== 'locked'

  const cards = [
    {
      key: 'starter',
      eyebrow: 'STARTER',
      title: isKo ? 'Starter 베타 신호' : 'Starter Beta Signals',
      description: isKo
        ? '대시보드에서 베타 신호 실험군을 먼저 확인하고, 핵심 업데이트를 가볍게 추적합니다.'
        : 'Preview the beta signal rollout in your dashboard and follow core updates with a lighter access tier.',
      highlights: isKo
        ? ['멤버 대시보드 베타 신호 카드', '신규 실험 배포 우선 확인', 'Pro 업그레이드 전 미리보기']
        : ['Dashboard beta signal cards', 'Early access to new experiments', 'Preview layer before Pro upgrade'],
      plan: starter,
      href: getPlanHref(locale, starter),
      status: statuses.starter,
      accent: 'from-emerald-500/18 via-cyan-500/10 to-transparent',
    },
    {
      key: 'pro',
      eyebrow: 'PRO',
      title: isKo ? 'Pro 베타 신호' : 'Pro Beta Signals',
      description: isKo
        ? 'Starter 범위를 포함해 더 깊은 베타 신호 묶음과 우선 노출 실험을 함께 받습니다.'
        : 'Includes Starter coverage plus deeper beta signal bundles and higher-priority experiment exposure.',
      highlights: isKo
        ? ['Starter 범위 전체 포함', '확장된 실험 신호 묶음', '상위 티어 롤아웃 우선권']
        : ['Includes all Starter access', 'Expanded experiment bundles', 'Priority rollout for higher-tier betas'],
      plan: pro,
      href: getPlanHref(locale, pro),
      status: statuses.pro,
      accent: 'from-amber-500/20 via-orange-500/12 to-transparent',
    },
  ] as const

  return (
    <section className="mb-12">
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2.5 py-1 text-[11px] font-semibold tracking-[0.22em] text-cyan-200">
            BETA SIGNALS
          </div>
          <h2 className="text-xl font-semibold text-white">
            {isKo ? 'Starter · Pro 베타 신호' : 'Starter · Pro Beta Signals'}
          </h2>
          <p className="mt-2 max-w-3xl text-sm text-gray-400">
            {isKo
              ? '현재 구독 상태에 따라 베타 신호 접근 범위와 업그레이드 가능 상태를 한눈에 확인할 수 있습니다.'
              : 'See your current beta-signal access at a glance and whether Starter or Pro rollout is already available on your account.'}
          </p>
        </div>
        <Link
          href={`/${locale}/products?type=subscription`}
          className="inline-flex items-center justify-center rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-white/10"
        >
          {isKo ? '플랜 보기' : 'View plans'}
        </Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {cards.map((card) => (
          <div
            key={card.key}
            className={`relative overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.9)]`}
          >
            <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${card.accent}`} />
            <div className="relative">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold tracking-[0.24em] text-gray-500">{card.eyebrow}</p>
                  <h3 className="mt-2 text-lg font-semibold text-white">{card.title}</h3>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-medium ${getStatusClasses(card.status)}`}>
                  {getStatusLabel(locale, card.status)}
                </span>
              </div>

              <p className="mb-5 text-sm leading-6 text-gray-300">{card.description}</p>

              <div className="mb-5 rounded-xl border border-white/8 bg-black/20 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-gray-500">
                  {isKo ? '연결 플랜' : 'Linked plan'}
                </p>
                <div className="mt-2 flex items-end justify-between gap-3">
                  <div>
                    <p className="text-base font-medium text-white">
                      {card.plan ? (card.plan.title_ko && isKo ? card.plan.title_ko : card.plan.title_en) : (isKo ? '곧 공개' : 'Coming soon')}
                    </p>
                    <p className="mt-1 text-sm text-cyan-200">{renderPrice(locale, card.plan)}</p>
                  </div>
                  {card.status === 'locked' ? (
                    <Link
                      href={card.href}
                      className="inline-flex items-center rounded-lg bg-white text-sm font-medium text-black px-3.5 py-2 transition-colors hover:bg-cyan-100"
                    >
                      {isKo ? '열기' : 'Open plan'}
                    </Link>
                  ) : (
                    <span className="text-sm font-medium text-cyan-200">
                      {card.status === 'included'
                        ? (isKo ? '현재 플랜에 포함됨' : 'Included in current plan')
                        : (isKo ? '접근 가능' : 'Access enabled')}
                    </span>
                  )}
                </div>
              </div>

              <div className="space-y-2 text-sm text-gray-400">
                {card.highlights.map((highlight) => (
                  <div key={highlight} className="flex items-start gap-2">
                    <span className="mt-1 text-cyan-300">●</span>
                    <span>{highlight}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.03] p-6">
        <div className="flex flex-col gap-3 border-b border-white/8 pb-4 md:flex-row md:items-start md:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">
              {isKo ? '최신 승인 베타 신호' : 'Latest Approved Beta Signal'}
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-gray-400">
              {isKo
                ? '베타 신호는 배치 생성 후 수동 승인 단계를 거쳐 공개됩니다. 생성 시점과 대시보드 반영 시점 사이에는 지연이 있을 수 있습니다.'
                : 'Beta signals are batch-generated and released only after manual approval. Dashboard delivery can lag behind raw generation time.'}
            </p>
          </div>
          <div className="rounded-xl border border-white/8 bg-black/20 px-4 py-3 text-sm text-gray-300">
            <p className="text-[11px] uppercase tracking-[0.2em] text-gray-500">
              {isKo ? '마지막 업데이트' : 'Last updated'}
            </p>
            <p className="mt-1 font-medium text-white">{formatDateTime(locale, signalSnapshot.lastUpdatedAt)}</p>
          </div>
        </div>

        <div className="mt-5">
          {!hasAccess && (
            <div className="rounded-2xl border border-dashed border-white/10 bg-black/10 p-6 text-center">
              <p className="text-base font-medium text-white">
                {isKo ? 'Starter 또는 Pro 구독 시 베타 신호가 열립니다.' : 'Starter or Pro access is required to unlock beta signals.'}
              </p>
              <p className="mt-2 text-sm text-gray-400">
                {isKo
                  ? '현재 계정에는 베타 신호 열람 권한이 없습니다. 위 플랜 카드에서 접근 상태를 확인할 수 있습니다.'
                  : 'Your account does not currently have beta-signal entitlement. Use the plan cards above to review access.'}
              </p>
            </div>
          )}

          {hasAccess && signalSnapshot.status === 'ready' && signalSnapshot.signal && (
            <div className="grid gap-4 lg:grid-cols-[1.35fr_0.9fr]">
              <div className="rounded-2xl border border-emerald-400/15 bg-gradient-to-br from-emerald-500/12 via-cyan-500/6 to-transparent p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold tracking-[0.24em] text-gray-500">
                      {signalSnapshot.signal.asset}
                    </p>
                    <h4 className="mt-2 text-2xl font-semibold text-white">
                      {signalSnapshot.signal.direction === 'long'
                        ? (isKo ? '롱 시그널' : 'Long signal')
                        : signalSnapshot.signal.direction === 'short'
                          ? (isKo ? '숏 시그널' : 'Short signal')
                          : (isKo ? '중립 시그널' : 'Neutral signal')}
                    </h4>
                  </div>
                  <span className="rounded-full border border-emerald-400/20 bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-200">
                    {isKo ? '승인됨' : 'Approved'}
                  </span>
                </div>
                <div className="mt-5 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-white/8 bg-black/20 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-gray-500">{isKo ? '신뢰도' : 'Confidence'}</p>
                    <p className="mt-2 text-xl font-semibold text-white">{formatPercent(signalSnapshot.signal.confidence)}</p>
                  </div>
                  <div className="rounded-xl border border-white/8 bg-black/20 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-gray-500">{isKo ? '예상 1일 수익률' : 'Predicted 1D return'}</p>
                    <p className="mt-2 text-xl font-semibold text-white">{formatPercent(signalSnapshot.signal.predicted_return_1d)}</p>
                  </div>
                  <div className="rounded-xl border border-white/8 bg-black/20 p-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-gray-500">{isKo ? '호라이즌' : 'Horizon'}</p>
                    <p className="mt-2 text-xl font-semibold text-white">
                      {signalSnapshot.signal.horizon ? `${signalSnapshot.signal.horizon}${isKo ? '일' : 'd'}` : '—'}
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-white/8 bg-black/10 p-6">
                <h4 className="text-base font-semibold text-white">
                  {isKo ? '신호 메타데이터' : 'Signal metadata'}
                </h4>
                <div className="mt-4 space-y-3 text-sm text-gray-400">
                  <div className="flex items-center justify-between gap-4">
                    <span>{isKo ? '시그널 기준일' : 'Signal date'}</span>
                    <span className="font-medium text-white">{formatDateTime(locale, signalSnapshot.signal.signal_date)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <span>{isKo ? '생성 시각' : 'Generated at'}</span>
                    <span className="font-medium text-white">{formatDateTime(locale, signalSnapshot.signal.generated_at)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {hasAccess && signalSnapshot.status === 'empty' && (
            <div className="rounded-2xl border border-sky-400/15 bg-sky-500/[0.06] p-6">
              <p className="text-base font-medium text-white">
                {isKo ? '아직 승인된 베타 신호가 없습니다.' : 'No approved beta signal is available yet.'}
              </p>
              <p className="mt-2 text-sm text-gray-300">
                {signalSnapshot.message ||
                  (isKo
                    ? '신호 승인 소스가 준비되면 이 영역에서 최신 승인 항목을 보여줍니다.'
                    : 'Once the approval-backed source is wired, the latest approved signal will appear here.')}
              </p>
            </div>
          )}

          {hasAccess && signalSnapshot.status === 'error' && (
            <div className="rounded-2xl border border-rose-400/15 bg-rose-500/[0.06] p-6">
              <p className="text-base font-medium text-white">
                {isKo ? '베타 신호를 불러오지 못했습니다.' : 'Unable to load the beta signal feed.'}
              </p>
              <p className="mt-2 text-sm text-gray-300">
                {signalSnapshot.message ||
                  (isKo
                    ? '승인된 베타 신호 소스를 확인한 뒤 다시 시도해 주세요.'
                    : 'Please verify the approved beta signal source and try again.')}
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
