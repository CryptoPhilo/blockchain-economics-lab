import { SupabaseClient } from '@supabase/supabase-js'
import type { TrackedProject, ProjectStatus } from '../types'

const MARKET_SNAPSHOT_SELECT_COLUMNS =
  'slug, price_usd, market_cap, change_24h, recorded_at, cmc_rank, cmc_symbol, cmc_name'
const LEGACY_MARKET_SNAPSHOT_SELECT_COLUMNS =
  'slug, price_usd, market_cap, change_24h, recorded_at, cmc_rank'
const SCOREBOARD_SNAPSHOT_CANDIDATE_COUNT = 30
const SCOREBOARD_SNAPSHOT_DATE_PAGE_SIZE = 1000
const SCOREBOARD_DAILY_SNAPSHOT_ROW_LIMIT_MULTIPLIER = 10

export type ScoreboardMarketSnapshotRow = {
  slug: string
  price_usd: number | string | null
  market_cap: number | string | null
  change_24h: number | string | null
  recorded_at: string
  cmc_rank: number | string | null
  cmc_symbol?: string | null
  cmc_name?: string | null
}

function isMissingCmcIdentityColumnError(error: { message?: string; code?: string } | null) {
  if (!error) return false
  if (error.code === '42703') return true
  return /cmc_(symbol|name)/i.test(error.message || '')
}

function toCanonicalRank(value: unknown, limit: number) {
  const rank = typeof value === 'number' ? value : Number(value)
  return Number.isInteger(rank) && rank >= 1 && rank <= limit ? rank : null
}

function isCompleteCanonicalRankSnapshot(rows: ScoreboardMarketSnapshotRow[], limit: number) {
  if (rows.length !== limit) return false

  const ranks = new Set(rows.map((row) => toCanonicalRank(row.cmc_rank, limit)))
  if (ranks.has(null) || ranks.size !== limit) return false

  for (let rank = 1; rank <= limit; rank += 1) {
    if (!ranks.has(rank)) return false
  }

  return true
}

function getRecordedAtDate(value: unknown) {
  if (typeof value !== 'string') return null
  const match = /^\d{4}-\d{2}-\d{2}/.exec(value)
  return match?.[0] ?? null
}

function getNextUtcDate(date: string) {
  const parsed = new Date(`${date}T00:00:00.000Z`)
  if (Number.isNaN(parsed.getTime())) return null
  parsed.setUTCDate(parsed.getUTCDate() + 1)
  return parsed.toISOString().slice(0, 10)
}

function latestRowsByCanonicalRank(rows: ScoreboardMarketSnapshotRow[], limit: number) {
  const latestByRank = new Map<number, ScoreboardMarketSnapshotRow>()

  for (const row of rows) {
    const rank = toCanonicalRank(row.cmc_rank, limit)
    if (!rank) continue

    const existing = latestByRank.get(rank)
    if (!existing || String(row.recorded_at) > String(existing.recorded_at)) {
      latestByRank.set(rank, row)
    }
  }

  return Array.from(latestByRank.values())
    .sort((a, b) => (toCanonicalRank(a.cmc_rank, limit) ?? 0) - (toCanonicalRank(b.cmc_rank, limit) ?? 0))
}

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

  async getLatestScoreboardMarketSnapshot(limit = 500): Promise<ScoreboardMarketSnapshotRow[]> {
    const snapshotDates: string[] = []
    const seenSnapshotDates = new Set<string>()
    const calendarDates: string[] = []
    const seenCalendarDates = new Set<string>()
    const maxCandidateRows = limit * SCOREBOARD_SNAPSHOT_CANDIDATE_COUNT

    for (
      let offset = 0;
      offset < maxCandidateRows && snapshotDates.length < SCOREBOARD_SNAPSHOT_CANDIDATE_COUNT;
      offset += SCOREBOARD_SNAPSHOT_DATE_PAGE_SIZE
    ) {
      const end = Math.min(offset + SCOREBOARD_SNAPSHOT_DATE_PAGE_SIZE - 1, maxCandidateRows - 1)
      const { data: snapshotCandidates, error: latestError } = await this.supabase
        .from('market_data_daily')
        .select('recorded_at')
        .gte('cmc_rank', 1)
        .lte('cmc_rank', limit)
        .order('recorded_at', { ascending: false })
        .range(offset, end)

      if (latestError) {
        throw new Error(`Failed to fetch scoreboard snapshot dates: ${latestError.message}`)
      }

      for (const row of snapshotCandidates || []) {
        if (!row.recorded_at || seenSnapshotDates.has(row.recorded_at)) continue
        seenSnapshotDates.add(row.recorded_at)
        snapshotDates.push(row.recorded_at)

        const calendarDate = getRecordedAtDate(row.recorded_at)
        if (calendarDate && !seenCalendarDates.has(calendarDate)) {
          seenCalendarDates.add(calendarDate)
          calendarDates.push(calendarDate)
        }

        if (snapshotDates.length >= SCOREBOARD_SNAPSHOT_CANDIDATE_COUNT) break
      }

      if (!snapshotCandidates || snapshotCandidates.length < SCOREBOARD_SNAPSHOT_DATE_PAGE_SIZE) break
    }

    if (snapshotDates.length === 0) {
      return []
    }

    const runSnapshotQuery = (recordedAt: string, selectColumns: string) => this.supabase
      .from('market_data_daily')
      .select(selectColumns)
      .eq('recorded_at', recordedAt)
      .gte('cmc_rank', 1)
      .lte('cmc_rank', limit)
      .order('cmc_rank', { ascending: true, nullsFirst: false })
      .limit(limit)

    const runDailySnapshotQuery = (recordedAtDate: string, selectColumns: string) => {
      const nextDate = getNextUtcDate(recordedAtDate)
      if (!nextDate) return null

      return this.supabase
        .from('market_data_daily')
        .select(selectColumns)
        .gte('recorded_at', recordedAtDate)
        .lt('recorded_at', nextDate)
        .gte('cmc_rank', 1)
        .lte('cmc_rank', limit)
        .order('recorded_at', { ascending: false })
        .limit(limit * SCOREBOARD_DAILY_SNAPSHOT_ROW_LIMIT_MULTIPLIER)
    }

    for (const recordedAt of snapshotDates) {
      let { data, error } = await runSnapshotQuery(recordedAt, MARKET_SNAPSHOT_SELECT_COLUMNS)

      if (isMissingCmcIdentityColumnError(error)) {
        ;({ data, error } = await runSnapshotQuery(recordedAt, LEGACY_MARKET_SNAPSHOT_SELECT_COLUMNS))
      }

      if (error) {
        throw new Error(`Failed to fetch scoreboard market snapshot: ${error.message}`)
      }

      const rows = (data || []) as unknown as ScoreboardMarketSnapshotRow[]
      if (isCompleteCanonicalRankSnapshot(rows, limit)) return rows
    }

    for (const recordedAtDate of calendarDates) {
      const dailyQuery = runDailySnapshotQuery(recordedAtDate, MARKET_SNAPSHOT_SELECT_COLUMNS)
      if (!dailyQuery) continue

      let { data, error } = await dailyQuery

      if (isMissingCmcIdentityColumnError(error)) {
        const legacyDailyQuery = runDailySnapshotQuery(recordedAtDate, LEGACY_MARKET_SNAPSHOT_SELECT_COLUMNS)
        if (legacyDailyQuery) {
          ;({ data, error } = await legacyDailyQuery)
        }
      }

      if (error) {
        throw new Error(`Failed to fetch scoreboard daily market snapshot: ${error.message}`)
      }

      const rows = latestRowsByCanonicalRank(
        (data || []) as unknown as ScoreboardMarketSnapshotRow[],
        limit,
      )
      if (isCompleteCanonicalRankSnapshot(rows, limit)) return rows
    }

    return []
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
