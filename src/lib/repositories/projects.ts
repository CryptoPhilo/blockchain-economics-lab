import { SupabaseClient } from '@supabase/supabase-js'
import type { TrackedProject, ProjectStatus } from '../types'

/**
 * Repository for project-related data access
 * Encapsulates all database queries for tracked projects
 */
export class ProjectsRepository {
  constructor(private supabase: SupabaseClient) {}

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

  async getLatestScoreboardMarketSnapshot(limit = 200) {
    const { data: latestSnapshot, error: latestError } = await this.supabase
      .from('market_data_daily')
      .select('recorded_at')
      .order('recorded_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (latestError) {
      throw new Error(`Failed to fetch latest scoreboard snapshot date: ${latestError.message}`)
    }

    if (!latestSnapshot?.recorded_at) {
      return []
    }

    const { data, error } = await this.supabase
      .from('market_data_daily')
      .select('slug, price_usd, market_cap, change_24h, recorded_at')
      .eq('recorded_at', latestSnapshot.recorded_at)
      .order('market_cap', { ascending: false, nullsFirst: false })
      .limit(limit)

    if (error) {
      throw new Error(`Failed to fetch scoreboard market snapshot: ${error.message}`)
    }

    return data || []
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
