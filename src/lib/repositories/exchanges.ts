import { SupabaseClient } from '@supabase/supabase-js'
import type { ScoreRow } from '@/lib/score-row'

const PAGE_SIZE = 1000
const ACTIVE_PROJECT_STATUSES = new Set(['active', 'monitoring_only'])

export type ExchangeRecord = {
  id: string
  slug: string
  name: string
  status: string
  website_url?: string | null
  country?: string | null
}

export type ExchangeProjectRecord = {
  id: string
  name: string
  slug: string
  symbol: string
  category: string | null
  market_cap_usd: number | string | null
  coingecko_id: string | null
  cmc_id: string | null
  aliases: string[] | null
  maturity_score: number | string | null
  last_econ_report_at: string | null
  last_maturity_report_at: string | null
  last_forensic_report_at: string | null
  status: string
}

export type ExchangeListingRecord = {
  listing_status: string
  exchange: ExchangeRecord | ExchangeRecord[] | null
  project: ExchangeProjectRecord | ExchangeProjectRecord[] | null
}

export type ExchangeAggregate = {
  id: string
  slug: string
  name: string
  status: string
  websiteUrl: string | null
  country: string | null
  listedProjectCount: number
  averageBceScore: number | null
  scoredProjectCount: number
}

export type ExchangeProjectListRow = ScoreRow

type LoadedListingRows = {
  rows: ExchangeListingRecord[]
}

function first<T>(value: T | T[] | null | undefined): T | null {
  if (Array.isArray(value)) return value[0] ?? null
  return value ?? null
}

function toNumber(value: unknown): number {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function toNullableNumber(value: unknown): number | null {
  if (value == null) return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string') {
    const numeric = Number(value)
    return Number.isFinite(numeric) ? numeric : null
  }
  return null
}

function normalizeKey(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : ''
}

function isActiveListing(row: ExchangeListingRecord) {
  const exchange = first(row.exchange)
  const project = first(row.project)

  return (
    row.listing_status === 'active'
    && exchange?.status === 'active'
    && !!project
    && ACTIVE_PROJECT_STATUSES.has(project.status)
  )
}

function getReportTypes(project: ExchangeProjectRecord) {
  const reportTypes: string[] = []
  if (project.last_econ_report_at) reportTypes.push('econ')
  if (project.last_maturity_report_at) reportTypes.push('maturity')
  if (project.last_forensic_report_at) reportTypes.push('forensic')
  return reportTypes
}

export function buildExchangeAggregates(rows: ExchangeListingRecord[]): ExchangeAggregate[] {
  const byExchange = new Map<string, {
    exchange: ExchangeRecord
    projects: Map<string, ExchangeProjectRecord>
  }>()

  for (const row of rows) {
    if (!isActiveListing(row)) continue

    const exchange = first(row.exchange)
    const project = first(row.project)
    if (!exchange || !project) continue

    const group = byExchange.get(exchange.id) ?? {
      exchange,
      projects: new Map<string, ExchangeProjectRecord>(),
    }
    if (!group.projects.has(project.id)) {
      group.projects.set(project.id, project)
    }
    byExchange.set(exchange.id, group)
  }

  return Array.from(byExchange.values())
    .map(({ exchange, projects }) => {
      const projectRows = Array.from(projects.values())
      const scores = projectRows
        .map((project) => toNullableNumber(project.maturity_score))
        .filter((score): score is number => score !== null)
      const scoreTotal = scores.reduce((total, score) => total + score, 0)

      return {
        id: exchange.id,
        slug: exchange.slug,
        name: exchange.name,
        status: exchange.status,
        websiteUrl: exchange.website_url ?? null,
        country: exchange.country ?? null,
        listedProjectCount: projectRows.length,
        averageBceScore: scores.length > 0 ? Number((scoreTotal / scores.length).toFixed(2)) : null,
        scoredProjectCount: scores.length,
      }
    })
    .sort((a, b) => (
      b.listedProjectCount - a.listedProjectCount
      || (b.averageBceScore ?? -1) - (a.averageBceScore ?? -1)
      || a.name.localeCompare(b.name)
    ))
}

export function buildExchangeProjectRows(
  rows: ExchangeListingRecord[],
  exchangeKey: string,
): { exchange: ExchangeRecord | null; projects: ExchangeProjectListRow[] } {
  const normalizedExchangeKey = normalizeKey(exchangeKey)
  const projects = new Map<string, ExchangeProjectRecord>()
  let matchedExchange: ExchangeRecord | null = null

  for (const row of rows) {
    if (!isActiveListing(row)) continue

    const exchange = first(row.exchange)
    const project = first(row.project)
    if (!exchange || !project) continue

    if (
      normalizeKey(exchange.slug) !== normalizedExchangeKey
      && normalizeKey(exchange.name) !== normalizedExchangeKey
    ) {
      continue
    }

    matchedExchange = exchange
    if (!projects.has(project.id)) {
      projects.set(project.id, project)
    }
  }

  const projectRows = Array.from(projects.values())
    .sort((a, b) => toNumber(b.market_cap_usd) - toNumber(a.market_cap_usd) || a.name.localeCompare(b.name))
    .map((project, index) => ({
      rank: index + 1,
      name: project.name,
      symbol: project.symbol,
      slug: project.slug,
      change24h: null,
      marketCap: toNumber(project.market_cap_usd),
      score: toNullableNumber(project.maturity_score),
      category: project.category ?? '',
      reportTypes: getReportTypes(project),
      reportDates: {
        econ: project.last_econ_report_at,
        maturity: project.last_maturity_report_at,
        forensic: project.last_forensic_report_at,
      },
    }))

  return { exchange: matchedExchange, projects: projectRows }
}

export class ExchangesRepository {
  constructor(private supabase: SupabaseClient) {}

  private async loadActiveListingRows(): Promise<LoadedListingRows> {
    const rows: ExchangeListingRecord[] = []

    for (let offset = 0; ; offset += PAGE_SIZE) {
      const query = this.supabase
        .from('exchange_project_listings')
        .select(`
          listing_status,
          exchange:exchanges!inner(id, slug, name, status, website_url, country),
          project:tracked_projects!inner(
            id, name, slug, symbol, category, market_cap_usd, coingecko_id, cmc_id, aliases,
            maturity_score, last_econ_report_at, last_maturity_report_at, last_forensic_report_at, status
          )
        `)
        .eq('listing_status', 'active')
        .eq('exchange.status', 'active')
        .in('project.status', ['active', 'monitoring_only'])
        .range(offset, offset + PAGE_SIZE - 1)

      const { data, error } = await query

      if (error) {
        throw new Error(`Failed to fetch exchange listings: ${error.message}`)
      }

      const batch = (data || []) as unknown as ExchangeListingRecord[]
      rows.push(...batch)

      if (batch.length < PAGE_SIZE) break
    }

    return { rows }
  }

  async getExchangeAggregates() {
    const { rows } = await this.loadActiveListingRows()
    return buildExchangeAggregates(rows)
  }

  async getExchangeProjects(exchangeKey: string) {
    const normalizedExchangeKey = normalizeKey(exchangeKey)
    const { rows } = await this.loadActiveListingRows()
    const result = buildExchangeProjectRows(rows, normalizedExchangeKey)

    return result.exchange ? result : { exchange: null, projects: [] }
  }
}

export function createExchangesRepository(supabase: SupabaseClient) {
  return new ExchangesRepository(supabase)
}
