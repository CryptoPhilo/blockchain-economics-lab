import type { Product, Subscription } from '@/lib/types'
import { resolveSignalPlans, resolveStatuses } from './DashboardBetaSignalsSection'

function createPlan(overrides: Partial<Product> = {}): Product {
  return {
    id: 'plan-default',
    type: 'subscription',
    status: 'published',
    slug: 'default-plan',
    title_en: 'Default plan',
    price_usd_cents: 1000,
    tags: [],
    featured: false,
    created_at: '2026-04-22T00:00:00.000Z',
    ...overrides,
  }
}

function createSubscription(overrides: Partial<Subscription> = {}): Subscription {
  return {
    id: 'sub-default',
    user_id: 'user-1',
    product_id: 'plan-default',
    status: 'active',
    payment_method: 'stripe',
    ...overrides,
  }
}

describe('DashboardBetaSignalsSection helpers', () => {
  it('identifies starter and pro plans only when each tier has a single explicit match', () => {
    const plans = [
      createPlan({ id: 'starter', slug: 'starter-beta', title_en: 'Starter Beta', tags: ['starter'] }),
      createPlan({ id: 'pro', slug: 'pro-beta', title_en: 'Pro Beta', price_usd_cents: 2900, tags: ['pro'] }),
      createPlan({ id: 'other', slug: 'research-membership', title_en: 'Research Membership', price_usd_cents: 4900 }),
    ]

    expect(resolveSignalPlans(plans)).toEqual({
      starter: expect.objectContaining({ id: 'starter' }),
      pro: expect.objectContaining({ id: 'pro' }),
    })
  })

  it('fails closed when a tier cannot be identified explicitly', () => {
    const plans = [
      createPlan({ id: 'lite', slug: 'lite-membership', title_en: 'Lite Membership' }),
      createPlan({ id: 'research', slug: 'research-membership', title_en: 'Research Membership', price_usd_cents: 2900 }),
    ]

    expect(resolveSignalPlans(plans)).toEqual({
      starter: null,
      pro: null,
    })
  })

  it('keeps unrelated subscriptions locked even if another subscription exists', () => {
    const { starter, pro } = resolveSignalPlans([
      createPlan({ id: 'starter', slug: 'starter-beta', title_en: 'Starter Beta', tags: ['starter'] }),
      createPlan({ id: 'pro', slug: 'pro-beta', title_en: 'Pro Beta', price_usd_cents: 2900, tags: ['pro'] }),
      createPlan({ id: 'vip', slug: 'vip-membership', title_en: 'VIP Membership', price_usd_cents: 9900 }),
    ])

    expect(
      resolveStatuses(
        [createSubscription({ product_id: 'vip', product: createPlan({ id: 'vip', slug: 'vip-membership', title_en: 'VIP Membership' }) })],
        starter,
        pro
      )
    ).toEqual({
      starter: 'locked',
      pro: 'locked',
    })
  })

  it('marks pro subscriptions as including starter access', () => {
    const { starter, pro } = resolveSignalPlans([
      createPlan({ id: 'starter', slug: 'starter-beta', title_en: 'Starter Beta', tags: ['starter'] }),
      createPlan({ id: 'pro', slug: 'pro-beta', title_en: 'Pro Beta', price_usd_cents: 2900, tags: ['pro'] }),
    ])

    expect(
      resolveStatuses(
        [createSubscription({ product_id: 'pro', product: createPlan({ id: 'pro', slug: 'pro-beta', title_en: 'Pro Beta', tags: ['pro'] }) })],
        starter,
        pro
      )
    ).toEqual({
      starter: 'included',
      pro: 'active',
    })
  })
})
