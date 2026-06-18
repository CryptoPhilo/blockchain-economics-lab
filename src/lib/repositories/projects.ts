import { SupabaseClient } from '@supabase/supabase-js'
import type { TrackedProject, ProjectStatus } from '../types'

const RECENT_CMC_SNAPSHOT_LOOKBACK = 5

/**
 * Repository for project-related data access
 * Encapsulates all database queries for tracked projects
 */
export class ProjectsRepository {
  constructor(private supabase: SupabaseClient) {}

  private async getLatestCmcSnapshotDate(rankLimit: number) {
    const { data, error } = await this.supabase
      .from('market_data_daily')
      .select('recorded_at')
      .eq('source', 'coinmarketcap')
      .gte('cmc_rank', 1)
      .lte('cmc_rank', rankLimit)
      .order('recorded_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (error) {
      throw new Error(`Failed to fetch latest CMC snapshot date: ${error.message}`)
    }

    return data?.recorded_at || null
  }

  private async getRecentCmcSnapshotDates(rankLimit: number, lookback = RECENT_CMC_SNAPSHOT_LOOKBACK) {
    const rowLimit = Math.max(rankLimit * lookback, lookback)
    const { data, error } = await this.supabase
      .from('market_data_daily')
      .select('recorded_at')
      .eq('source', 'coinmarketcap')
      .gte('cmc_rank', 1)
      .lte('cmc_rank', rankLimit)
      .order('recorded_at', { ascending: false })
      .limit(rowLimit)

    if (error) {
      throw new Error(`Failed to fetch recent CMC snapshot dates: ${error.message}`)
    }

    const recordedAts: string[] = []
    for (const row of data || []) {
      if (!row.recorded_at || recordedAts.includes(row.recorded_at)) continue
      recordedAts.push(row.recorded_at)
      if (recordedAts.length >= lookback) break
    }

    return recordedAts
  }

  private hasContiguousCmcRanks(rows: Array<{ cmc_rank: number | string | null }>, rankLimit: number) {
    if (rows.length !== rankLimit) return false

    const ranks = new Set<number>()
    for (const row of rows) {
      const rank = Number(row.cmc_rank)
      if (!Number.isInteger(rank) || rank < 1 || rank > rankLimit || ranks.has(rank)) {
        return false
      }
      ranks.add(rank)
    }

    return ranks.size === rankLimit
  }

  private async getScoreboardMarketSnapshotForDate(recordedAt: string, limit: number) {
    const { data, error } = await this.supabase
      .from('market_data_daily')
      .select('slug, price_usd, market_cap, change_24h, recorded_at, cmc_rank')
      .eq('recorded_at', recordedAt)
      .eq('source', 'coinmarketcap')
      .gte('cmc_rank', 1)
      .lte('cmc_rank', 500)
      .order('cmc_rank', { ascending: true, nullsFirst: false })
      .limit(limit)

    if (error) {
      throw new Error(`Failed to fetch scoreboard market snapshot: ${error.message}`)
    }

    return data || []
  }

  private async getCmcRanksForDate(recordedAt: string, limit: number) {
    const { data, error } = await this.supabase
      .from('market_data_daily')
      .select('slug, cmc_rank')
      .eq('recorded_at', recordedAt)
      .eq('source', 'coinmarketcap')
      .gte('cmc_rank', 1)
      .lte('cmc_rank', limit)
      .order('cmc_rank', { ascending: true, nullsFirst: false })
      .limit(limit)

    if (error) {
      throw new Error(`Failed to fetch latest CMC ranks: ${error.message}`)
    }

    return data || []
  }

  async getProjectsForScoreboard() {
    const { data, error } = await this.supabase
      .from('tracked_projects')
      .select(`
        id, name, slug, symbol, category,
        market_cap_usd, coingecko_id, cmc_id, aliases, maturity_score,
        last_econ_report_at, last_maturity_report_at, last_forensic_report_at
      `)
      .in('status', ['active', 'monitoring_only'])
      .order('market_cap_usd', { ascending: false, nullsFirst: false })

    if (error) {
      throw new Error(`Failed to fetch scoreboard projects: ${error.message}`)
    }

    return data || []
  }

  async getExchangeProjects() {
    const { data, error } = await this.supabase
      .from('tracked_projects')
      .select(`
        id, name, slug, symbol, category,
        market_cap_usd, coingecko_id, cmc_id, aliases, maturity_score,
        last_econ_report_at, last_maturity_report_at, last_forensic_report_at
      `)
      .in('status', ['active', 'monitoring_only'])
      .ilike('category', '%exchange%')
      .order('name', { ascending: true })

    if (error) {
      throw new Error(`Failed to fetch exchange projects: ${error.message}`)
    }

    return data || []
  }

  async getExchangeProjectBySlug(slug: string) {
    const { data, error } = await this.supabase
      .from('tracked_projects')
      .select(`
        id, name, slug, symbol, category,
        market_cap_usd, coingecko_id, cmc_id, aliases, maturity_score,
        last_econ_report_at, last_maturity_report_at, last_forensic_report_at
      `)
      .eq('slug', slug)
      .in('status', ['active', 'monitoring_only'])
      .ilike('category', '%exchange%')
      .maybeSingle()

    if (error) {
      throw new Error(`Failed to fetch exchange project: ${error.message}`)
    }

    return data || null
  }

  async getLatestScoreboardMarketSnapshot(limit = 500) {
    const latestRecordedAt = await this.getLatestCmcSnapshotDate(500)
    if (!latestRecordedAt) return []

    const latestRows = await this.getScoreboardMarketSnapshotForDate(latestRecordedAt, limit)
    if (this.hasContiguousCmcRanks(latestRows, 500)) {
      return latestRows
    }

    const snapshotDates = await this.getRecentCmcSnapshotDates(500)
    for (const recordedAt of snapshotDates) {
      if (recordedAt === latestRecordedAt) continue
      const rows = await this.getScoreboardMarketSnapshotForDate(recordedAt, limit)
      if (this.hasContiguousCmcRanks(rows, 500)) {
        return rows
      }
    }

    return latestRows
  }

  async getLatestCmcRanks(limit = 500) {
    const latestRecordedAt = await this.getLatestCmcSnapshotDate(limit)
    if (!latestRecordedAt) return []

    const latestRows = await this.getCmcRanksForDate(latestRecordedAt, limit)
    if (this.hasContiguousCmcRanks(latestRows, limit)) {
      return latestRows
    }

    const snapshotDates = await this.getRecentCmcSnapshotDates(limit)
    for (const recordedAt of snapshotDates) {
      if (recordedAt === latestRecordedAt) continue
      const rows = await this.getCmcRanksForDate(recordedAt, limit)
      if (this.hasContiguousCmcRanks(rows, limit)) {
        return rows
      }
    }

    return latestRows
  }

  /**
   * Fetch a single project by slug
   */
  async getProjectBySlug(slug: string) {
    const { data, error } = await this.supabase
      .from('tracked_projects')
      .select('*')
      .eq('slug', slug)
      .single()

    if (error) {
      return null
    }

    return data as TrackedProject | null
  }

  /**
   * Fetch a single project by ID
   */
  async getProjectById(projectId: string) {
    const { data, error } = await this.supabase
      .from('tracked_projects')
      .select('*')
      .eq('id', projectId)
      .single()

    if (error) {
      return null
    }

    return data as TrackedProject | null
  }

  /**
   * Fetch projects with filters
   */
  async getProjects(params: {
    status?: ProjectStatus | ProjectStatus[]
    category?: string
    forensicMonitoring?: boolean
    limit?: number
    offset?: number
  } = {}) {
    const {
      status = ['active', 'monitoring_only'],
      category,
      forensicMonitoring,
      limit = 50,
      offset = 0
    } = params

    let query = this.supabase
      .from('tracked_projects')
      .select('*')

    // Apply status filter
    if (Array.isArray(status)) {
      query = query.in('status', status)
    } else {
      query = query.eq('status', status)
    }

    // Apply category filter
    if (category) {
      query = query.eq('category', category)
    }

    // Apply forensic monitoring filter
    if (forensicMonitoring !== undefined) {
      query = query.eq('forensic_monitoring', forensicMonitoring)
    }

    // Apply pagination
    query = query
      .order('name', { ascending: true })
      .range(offset, offset + limit - 1)

    const { data, error } = await query

    if (error) {
      throw new Error(`Failed to fetch projects: ${error.message}`)
    }

    return (data || []) as TrackedProject[]
  }

  /**
   * Search projects by name or symbol
   */
  async searchProjects(searchTerm: string, limit = 10) {
    const { data, error } = await this.supabase
      .from('tracked_projects')
      .select('id, name, slug, symbol, category')
      .or(`name.ilike.%${searchTerm}%,symbol.ilike.%${searchTerm}%`)
      .in('status', ['active', 'monitoring_only'])
      .order('name', { ascending: true })
      .limit(limit)

    if (error) {
      throw new Error(`Failed to search projects: ${error.message}`)
    }

    return (data || []) as Pick<TrackedProject, 'id' | 'name' | 'slug' | 'symbol' | 'category'>[]
  }
}

/**
 * Create a projects repository instance
 */
export function createProjectsRepository(supabase: SupabaseClient) {
  return new ProjectsRepository(supabase)
}
