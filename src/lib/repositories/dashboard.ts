import { SupabaseClient } from '@supabase/supabase-js'
import { readFile } from 'fs/promises'
import path from 'path'
import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import { filterPublicProducts } from '@/lib/product-access'
import { createTradingSignalsAdminRepository } from '@/lib/repositories/trading-signals'
import type { Order, Product, Subscription, UserLibraryItem } from '../types'

interface DashboardProfile {
  onboarding_completed: boolean
  referral_code?: string | null
  referred_by?: string | null
}

export interface DashboardLibraryItem extends UserLibraryItem {
  report_id?: string
}

export interface DashboardBetaSignal {
  asset: string
  direction: string
  confidence: number | null
  signal_date: string | null
  generated_at: string | null
  horizon: number | null
  predicted_return_1d: number | null
}

export interface DashboardBetaSignalSnapshot {
  status: 'ready' | 'empty' | 'error'
  signal: DashboardBetaSignal | null
  lastUpdatedAt: string | null
  message?: string
}

export class DashboardRepository {
  constructor(private supabase: SupabaseClient) {}

  async getProfile(userId: string) {
    const { data, error } = await this.supabase
      .from('profiles')
      .select('onboarding_completed, referral_code, referred_by')
      .eq('id', userId)
      .maybeSingle()

    if (error) {
      throw new Error(`Failed to fetch profile: ${error.message}`)
    }

    return data as DashboardProfile | null
  }

  async updateProfile(userId: string, updates: Partial<DashboardProfile>) {
    const { error } = await this.supabase
      .from('profiles')
      .update(updates)
      .eq('id', userId)

    if (error) {
      throw new Error(`Failed to update profile: ${error.message}`)
    }
  }

  async findReferrerByCode(code: string) {
    const { data, error } = await this.supabase
      .from('profiles')
      .select('id')
      .eq('referral_code', code)
      .maybeSingle()

    if (error) {
      throw new Error(`Failed to fetch referrer: ${error.message}`)
    }

    return data as { id: string } | null
  }

  async getExistingMemberReferral(referredId: string) {
    const { data, error } = await this.supabase
      .from('member_referrals')
      .select('id')
      .eq('referred_id', referredId)
      .maybeSingle()

    if (error) {
      throw new Error(`Failed to fetch referral: ${error.message}`)
    }

    return data as { id: string } | null
  }

  async createMemberReferral(input: {
    referrerId: string
    referredId: string
    referralCode: string
    status: string
    rewardType: string
    rewardValue: number
  }) {
    const { error } = await this.supabase.from('member_referrals').insert({
      referrer_id: input.referrerId,
      referred_id: input.referredId,
      referral_code: input.referralCode,
      status: input.status,
      reward_type: input.rewardType,
      reward_value: input.rewardValue,
    })

    if (error) {
      throw new Error(`Failed to create referral: ${error.message}`)
    }
  }

  async getUserLibrary(userId: string) {
    const { data, error } = await this.supabase
      .from('user_library')
      .select('*, product:products(*)')
      .eq('user_id', userId)
      .order('access_granted_at', { ascending: false })

    if (error) {
      throw new Error(`Failed to fetch library: ${error.message}`)
    }

    const library = (data || []) as DashboardLibraryItem[]
    const productIds = [...new Set(library.map((item) => item.product_id).filter(Boolean))]

    if (productIds.length === 0) {
      return library
    }

    const { data: reports, error: reportsError } = await this.supabase
      .from('project_reports')
      .select('id, product_id, published_at, created_at')
      .in('product_id', productIds)
      .order('published_at', { ascending: false, nullsFirst: false })
      .order('created_at', { ascending: false, nullsFirst: false })

    if (reportsError) {
      throw new Error(`Failed to fetch library reports: ${reportsError.message}`)
    }

    const latestReportByProduct = new Map<string, string>()
    for (const report of reports || []) {
      if (!report.product_id || latestReportByProduct.has(report.product_id)) {
        continue
      }
      latestReportByProduct.set(report.product_id, report.id)
    }

    return library.map((item) => ({
      ...item,
      report_id: latestReportByProduct.get(item.product_id),
    }))
  }

  async getActiveSubscriptions(userId: string) {
    const { data, error } = await this.supabase
      .from('subscriptions')
      .select('*, product:products(*)')
      .eq('user_id', userId)
      .eq('status', 'active')

    if (error) {
      throw new Error(`Failed to fetch subscriptions: ${error.message}`)
    }

    return (data || []) as Subscription[]
  }

  async getPublishedSubscriptionPlans() {
    const { data, error } = await this.supabase
      .from('products')
      .select('*')
      .eq('type', 'subscription')
      .eq('status', 'published')
      .order('price_usd_cents', { ascending: true })

    if (error) {
      throw new Error(`Failed to fetch subscription plans: ${error.message}`)
    }

    return filterPublicProducts((data || []) as Product[])
  }

  async getLatestApprovedBetaSignal(): Promise<DashboardBetaSignalSnapshot> {
    try {
      const projectId = process.env.BETA_SIGNAL_PROJECT_ID

      if (projectId) {
        const adminSupabase = createSupabaseAdminClient()
        const repository = createTradingSignalsAdminRepository(adminSupabase)
        const signal = await repository.getLatestApprovedSignal(projectId)

        if (signal) {
          return {
            status: 'ready',
            signal: {
              asset: signal.project?.symbol || signal.project?.name || 'Unknown',
              direction: signal.direction,
              confidence: signal.confidence ?? null,
              signal_date: signal.signal_date ?? null,
              generated_at: signal.run?.generated_at ?? signal.approved_at ?? null,
              horizon: signal.horizon_days ?? null,
              predicted_return_1d: signal.predicted_return_1d ?? null,
            },
            lastUpdatedAt: signal.approved_at ?? signal.run?.generated_at ?? signal.created_at,
          }
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown beta signal error'
      return {
        status: 'error',
        signal: null,
        lastUpdatedAt: null,
        message,
      }
    }

    const configuredPath = process.env.BETA_SIGNAL_APPROVED_PATH

    if (!configuredPath) {
      return {
        status: 'empty',
        signal: null,
        lastUpdatedAt: null,
        message: 'No approved beta signal source is configured yet.',
      }
    }

    const resolvedPath = path.isAbsolute(configuredPath)
      ? configuredPath
      : path.join(process.cwd(), configuredPath)

    try {
      const raw = await readFile(resolvedPath, 'utf8')
      const parsed = JSON.parse(raw)
      const records = Array.isArray(parsed) ? parsed : []

      if (records.length === 0) {
        return {
          status: 'empty',
          signal: null,
          lastUpdatedAt: null,
          message: 'The approved beta signal source is empty.',
        }
      }

      const latest = [...records]
        .map((record) => ({
          asset: typeof record.asset === 'string' ? record.asset : 'Unknown',
          direction: typeof record.direction === 'string' ? record.direction : 'neutral',
          confidence: typeof record.confidence === 'number' ? record.confidence : null,
          signal_date: typeof record.signal_date === 'string' ? record.signal_date : null,
          generated_at: typeof record.generated_at === 'string' ? record.generated_at : null,
          horizon: typeof record.horizon === 'number' ? record.horizon : null,
          predicted_return_1d: typeof record.predicted_return_1d === 'number' ? record.predicted_return_1d : null,
        }))
        .sort((left, right) => {
          const leftTs = new Date(left.generated_at || left.signal_date || 0).getTime()
          const rightTs = new Date(right.generated_at || right.signal_date || 0).getTime()
          return rightTs - leftTs
        })[0]

      return {
        status: 'ready',
        signal: latest,
        lastUpdatedAt: latest.generated_at || latest.signal_date,
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown beta signal error'
      return {
        status: 'error',
        signal: null,
        lastUpdatedAt: null,
        message,
      }
    }
  }

  async getRecentOrders(userId: string, limit = 10) {
    const { data, error } = await this.supabase
      .from('orders')
      .select('*, items:order_items(*, product:products(*))')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) {
      throw new Error(`Failed to fetch orders: ${error.message}`)
    }

    return (data || []) as Order[]
  }
}

export function createDashboardRepository(supabase: SupabaseClient) {
  return new DashboardRepository(supabase)
}
