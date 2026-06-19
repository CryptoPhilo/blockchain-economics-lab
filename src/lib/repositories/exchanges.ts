import { SupabaseClient } from '@supabase/supabase-js'
import type { ScoreRow } from '@/lib/score-row'
import { findCmcTop30ExchangeReference } from '@/lib/exchange-top30'
import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import {
  applyProjectReportAvailabilityAliases,
  buildReportAvailabilityByProjectId,
  createEmptyReportAvailability,
  fetchVisibleReportsForProjectIds,
  getProjectReportAvailabilityKeys,
  type ReportAvailability,
  type ProjectReportAvailabilityCandidate,
} from '@/lib/report-availability'

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
  cmc_rank?: number | string | null
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

export type ExchangeAggregateSource = {
  exchanges: ExchangeRecord[]
  listings: ExchangeListingRecord[]
}

export type ExchangeAggregate = {
  id: string
  slug: string
  name: string
  status: string
  websiteUrl: string | null
  country: string | null
  listedProjectCount: number
  bceExchangeScore: number | null
  bceExchangeScoreFormulaVersion: typeof BCE_EXCHANGE_SCORE_FORMULA_VERSION
  bceExchangeScoreComponents: BceExchangeScoreComponents
  scoredProjectCount: number
}

export type ExchangeProjectListRow = ScoreRow

export const BCE_EXCHANGE_SCORE_FORMULA_VERSION = 'bce-exchange-score-v1' as const

export type BceExchangeScoreComponents = {
  coreBceQuality: number
  rankQuality: number
  scoreCoverage: number
  longTailPenalty: number
  listedProjectCount: number
  scoredProjectCount: number
  longTailRatio: number
}

export type BceExchangeScoreResult = {
  bceExchangeScore: number | null
  bceExchangeScoreFormulaVersion: typeof BCE_EXCHANGE_SCORE_FORMULA_VERSION
  bceExchangeScoreComponents: BceExchangeScoreComponents
}

type LoadedListingRows = {
  rows: ExchangeListingRecord[]
}

export { applyProjectReportAvailabilityAliases } from '@/lib/report-availability'

type ProjectReportAvailabilityCandidateWithStatus = ProjectReportAvailabilityCandidate & Pick<
  ExchangeProjectRecord,
  'status'
>

type LatestCmcMarketDataRow = {
  slug: string
  cmc_rank: number | string | null
  market_cap: number | string | null
}

type ExchangeProjectMarketDataKey = Pick<ExchangeProjectRecord, 'slug' | 'coingecko_id' | 'cmc_id' | 'aliases'>

type CmcMarketData = {
  cmcRank: number
  marketCap: number | null
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

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function roundScore(value: number) {
  return Number(value.toFixed(2))
}

function getConservativeCmcRank(project: ExchangeProjectRecord): number {
  const rank = toNullableNumber(project.cmc_rank)
  return rank !== null && rank > 0 ? rank : 5000
}

function getRankScore(project: ExchangeProjectRecord): number {
  const rank = toNullableNumber(project.cmc_rank)
  if (rank === null || rank < 1 || rank > 5000) return 0
  return clamp(100 * (1 - Math.log10(rank) / Math.log10(5000)), 0, 100)
}

export function calculateBceExchangeScore(projectRows: ExchangeProjectRecord[]): BceExchangeScoreResult {
  const listedProjectCount = projectRows.length
  const scoredRows = projectRows
    .map((project) => ({
      project,
      score: toNullableNumber(project.maturity_score),
    }))
    .filter((row): row is { project: ExchangeProjectRecord; score: number } => row.score !== null)

  const scoredProjectCount = scoredRows.length
  const longTailCount = projectRows.filter((project) => {
    const rank = toNullableNumber(project.cmc_rank)
    return rank === null || rank > 1000
  }).length
  const longTailRatio = listedProjectCount > 0 ? longTailCount / listedProjectCount : 0

  const weightedScore = scoredRows.reduce((total, { project, score }) => {
    const weight = 1 / Math.log2(getConservativeCmcRank(project) + 1)
    return total + (score * weight)
  }, 0)
  const weightTotal = scoredRows.reduce((total, { project }) => (
    total + (1 / Math.log2(getConservativeCmcRank(project) + 1))
  ), 0)

  const coreBceQuality = weightTotal > 0 ? weightedScore / weightTotal : 0
  const rankQuality = listedProjectCount > 0
    ? projectRows.reduce((total, project) => total + getRankScore(project), 0) / listedProjectCount
    : 0
  const scoreCoverage = listedProjectCount > 0
    ? 100 * Math.sqrt(scoredProjectCount / listedProjectCount)
    : 0
  const longTailPenalty = 15 * clamp((longTailRatio - 0.30) / 0.70, 0, 1)

  const components: BceExchangeScoreComponents = {
    coreBceQuality: roundScore(coreBceQuality),
    rankQuality: roundScore(rankQuality),
    scoreCoverage: roundScore(scoreCoverage),
    longTailPenalty: roundScore(longTailPenalty),
    listedProjectCount,
    scoredProjectCount,
    longTailRatio: roundScore(longTailRatio),
  }

  if (listedProjectCount === 0) {
    return {
      bceExchangeScore: null,
      bceExchangeScoreFormulaVersion: BCE_EXCHANGE_SCORE_FORMULA_VERSION,
      bceExchangeScoreComponents: components,
    }
  }

  const bceExchangeScore = clamp(
    (0.60 * coreBceQuality)
    + (0.25 * rankQuality)
    + (0.15 * scoreCoverage)
    - longTailPenalty,
    0,
    100,
  )

  return {
    bceExchangeScore: roundScore(bceExchangeScore),
    bceExchangeScoreFormulaVersion: BCE_EXCHANGE_SCORE_FORMULA_VERSION,
    bceExchangeScoreComponents: components,
  }
}

function normalizeKey(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : ''
}

function normalizeNullableKey(value: unknown): string | null {
  const normalized = normalizeKey(value)
  return normalized || null
}

function getProjectMarketDataKeys(project: ExchangeProjectMarketDataKey): string[] {
  // CoinGecko ids are aliases only: the rank value must still come from a
  // market_data_daily row whose source is CoinMarketCap and field is cmc_rank.
  return Array.from(new Set([
    normalizeNullableKey(project.slug),
    normalizeNullableKey(project.coingecko_id),
    normalizeNullableKey(project.cmc_id),
    ...(Array.isArray(project.aliases)
      ? project.aliases.map(normalizeNullableKey)
      : []),
  ].filter((key): key is string => !!key)))
}

function getProjectCmcMarketData(
  project: ExchangeProjectMarketDataKey,
  cmcMarketDataByKey: Map<string, CmcMarketData>,
) {
  for (const key of getProjectMarketDataKeys(project)) {
    const marketData = cmcMarketDataByKey.get(key)
    if (marketData) return marketData
  }

  return null
}

export function getMissingProjectMarketDataKeys(
  rows: ExchangeListingRecord[],
  cmcMarketDataByKey: Map<string, CmcMarketData>,
): string[] {
  const keys = new Set<string>()

  for (const row of rows) {
    const project = first(row.project)
    if (!project || getProjectCmcMarketData(project, cmcMarketDataByKey) !== null) continue

    for (const key of getProjectMarketDataKeys(project)) {
      keys.add(key)
    }
  }

  return Array.from(keys)
}

function exchangeMatches(exchange: ExchangeRecord, exchangeKey: string): boolean {
  const normalizedExchangeKey = normalizeKey(exchangeKey)
  const reference = findCmcTop30ExchangeReference(exchange.slug) ?? findCmcTop30ExchangeReference(exchange.name)
  const candidateKeys = [
    exchange.slug,
    exchange.name,
    reference?.slug,
    reference?.cmcName,
    reference?.coingeckoId,
    ...(reference?.aliases ?? []),
  ]

  return candidateKeys.some((key) => normalizeKey(key) === normalizedExchangeKey)
}

function getCanonicalExchangeKey(exchange: ExchangeRecord): string {
  const reference = findCmcTop30ExchangeReference(exchange.slug) ?? findCmcTop30ExchangeReference(exchange.name)
  return normalizeKey(reference?.slug ?? exchange.slug ?? exchange.id)
}

function isCanonicalExchangeRow(exchange: ExchangeRecord): boolean {
  const reference = findCmcTop30ExchangeReference(exchange.slug) ?? findCmcTop30ExchangeReference(exchange.name)
  return !!reference && normalizeKey(exchange.slug) === normalizeKey(reference.slug)
}

function choosePreferredExchange(current: ExchangeRecord, candidate: ExchangeRecord): ExchangeRecord {
  if (isCanonicalExchangeRow(candidate) && !isCanonicalExchangeRow(current)) return candidate
  return current
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

export function applyLatestCmcRanks(
  rows: ExchangeListingRecord[],
  cmcMarketDataByKey: Map<string, CmcMarketData>,
): ExchangeListingRecord[] {
  const applyCmcMarketData = (project: ExchangeProjectRecord): ExchangeProjectRecord => {
    const marketData = getProjectCmcMarketData(project, cmcMarketDataByKey)
    if (!marketData) return project

    return {
      ...project,
      cmc_rank: marketData.cmcRank,
      market_cap_usd: marketData.marketCap ?? project.market_cap_usd ?? null,
    }
  }

  return rows.map((row) => {
    const project = first(row.project)
    if (!project) return row

    const marketData = getProjectCmcMarketData(project, cmcMarketDataByKey)
    if (marketData === null) return row

    return {
      ...row,
      project: Array.isArray(row.project)
        ? row.project.map(applyCmcMarketData)
        : applyCmcMarketData(project),
    }
  })
}

function getReportTypes(project: ExchangeProjectRecord) {
  const reportTypes: string[] = []
  if (project.last_econ_report_at) reportTypes.push('econ')
  if (project.last_maturity_report_at) reportTypes.push('maturity')
  if (project.last_forensic_report_at) reportTypes.push('forensic')
  return reportTypes
}

function createFallbackReportAvailability(project: ExchangeProjectRecord): ReportAvailability {
  return {
    reportTypes: getReportTypes(project),
    reportDates: {
      econ: project.last_econ_report_at,
      maturity: project.last_maturity_report_at,
      forensic: project.last_forensic_report_at,
    },
  }
}

function pickLatestReportDate(...dates: Array<string | null | undefined>) {
  const validDates = dates.filter((date): date is string => !!date)
  if (validDates.length === 0) return null

  return validDates.reduce((latest, candidate) => (
    new Date(candidate).getTime() > new Date(latest).getTime() ? candidate : latest
  ))
}

function mergeReportAvailability(
  fallback: ReportAvailability,
  live: ReportAvailability | undefined,
): ReportAvailability {
  if (!live) return fallback

  const reportTypes = ['econ', 'maturity', 'forensic'].filter((reportType) => (
    fallback.reportTypes.includes(reportType) || live.reportTypes.includes(reportType)
  ))

  return {
    reportTypes,
    reportDates: {
      econ: pickLatestReportDate(live.reportDates.econ, fallback.reportDates.econ),
      maturity: pickLatestReportDate(live.reportDates.maturity, fallback.reportDates.maturity),
      forensic: pickLatestReportDate(live.reportDates.forensic, fallback.reportDates.forensic),
    },
  }
}

export function buildExchangeAggregates(
  input: ExchangeListingRecord[] | ExchangeAggregateSource,
): ExchangeAggregate[] {
  const exchanges = Array.isArray(input) ? [] : input.exchanges
  const rows = Array.isArray(input) ? input : input.listings
  const byExchange = new Map<string, {
    exchange: ExchangeRecord
    projects: Map<string, ExchangeProjectRecord>
  }>()

  for (const exchange of exchanges) {
    if (exchange.status !== 'active') continue
    const exchangeKey = getCanonicalExchangeKey(exchange)
    const group = byExchange.get(exchangeKey)
    if (group) {
      group.exchange = choosePreferredExchange(group.exchange, exchange)
    } else {
      byExchange.set(exchangeKey, {
        exchange,
        projects: new Map<string, ExchangeProjectRecord>(),
      })
    }
  }

  for (const row of rows) {
    if (!isActiveListing(row)) continue

    const exchange = first(row.exchange)
    const project = first(row.project)
    if (!exchange || !project) continue

    const exchangeKey = getCanonicalExchangeKey(exchange)
    const group = byExchange.get(exchangeKey) ?? {
      exchange,
      projects: new Map<string, ExchangeProjectRecord>(),
    }
    group.exchange = choosePreferredExchange(group.exchange, exchange)
    if (!group.projects.has(project.id)) {
      group.projects.set(project.id, project)
    }
    byExchange.set(exchangeKey, group)
  }

  return Array.from(byExchange.values())
    .map(({ exchange, projects }) => {
      const projectRows = Array.from(projects.values())
      const bceExchangeScore = calculateBceExchangeScore(projectRows)

      return {
        id: exchange.id,
        slug: exchange.slug,
        name: exchange.name,
        status: exchange.status,
        websiteUrl: exchange.website_url ?? null,
        country: exchange.country ?? null,
        listedProjectCount: projectRows.length,
        ...bceExchangeScore,
        scoredProjectCount: bceExchangeScore.bceExchangeScoreComponents.scoredProjectCount,
      }
    })
    .filter((exchange) => exchange.listedProjectCount > 0)
    .sort((a, b) => (
      getCmcRank(a) - getCmcRank(b)
      || (b.bceExchangeScore ?? -1) - (a.bceExchangeScore ?? -1)
      || b.listedProjectCount - a.listedProjectCount
      || a.name.localeCompare(b.name)
    ))
}

export function buildExchangeProjectRows(
  rows: ExchangeListingRecord[],
  exchangeKey: string,
  availabilityByProjectId?: Map<string, ReportAvailability>,
): { exchange: ExchangeRecord | null; projects: ExchangeProjectListRow[] } {
  const normalizedExchangeKey = normalizeKey(exchangeKey)
  const projects = new Map<string, ExchangeProjectRecord>()
  let matchedExchange: ExchangeRecord | null = null

  for (const row of rows) {
    if (!isActiveListing(row)) continue

    const exchange = first(row.exchange)
    const project = first(row.project)
    if (!exchange || !project) continue

    if (!exchangeMatches(exchange, normalizedExchangeKey)) {
      continue
    }

    matchedExchange = matchedExchange ? choosePreferredExchange(matchedExchange, exchange) : exchange
    if (!projects.has(project.id)) {
      projects.set(project.id, project)
    }
  }

  const projectRows = Array.from(projects.values())
    .sort((a, b) => {
      const rankA = toNullableNumber(a.cmc_rank)
      const rankB = toNullableNumber(b.cmc_rank)
      const comparableRankA = rankA ?? Number.MAX_SAFE_INTEGER
      const comparableRankB = rankB ?? Number.MAX_SAFE_INTEGER
      return comparableRankA - comparableRankB
        || toNumber(b.market_cap_usd) - toNumber(a.market_cap_usd)
        || a.name.localeCompare(b.name)
    })
    .map((project) => {
      const cmcRank = toNullableNumber(project.cmc_rank)
      const fallbackAvailability = createFallbackReportAvailability(project)
      const reportAvailability = availabilityByProjectId
        ? mergeReportAvailability(
          fallbackAvailability,
          availabilityByProjectId.get(project.id) ?? createEmptyReportAvailability(),
        )
        : fallbackAvailability

      return {
        rank: cmcRank,
        name: project.name,
        symbol: project.symbol,
        slug: project.slug,
        cmcRank,
        change24h: null,
        marketCap: toNumber(project.market_cap_usd),
        score: toNullableNumber(project.maturity_score),
        category: project.category ?? '',
        reportTypes: reportAvailability.reportTypes,
        reportDates: reportAvailability.reportDates,
      }
    })

  return { exchange: matchedExchange, projects: projectRows }
}

function getCmcRank(exchange: Pick<ExchangeAggregate, 'slug' | 'name'>): number {
  return findCmcTop30ExchangeReference(exchange.slug)?.cmcRank
    ?? findCmcTop30ExchangeReference(exchange.name)?.cmcRank
    ?? Number.MAX_SAFE_INTEGER
}

export class ExchangesRepository {
  constructor(private supabase: SupabaseClient) {}

  private async loadActiveExchanges(): Promise<ExchangeRecord[]> {
    const rows: ExchangeRecord[] = []

    for (let offset = 0; ; offset += PAGE_SIZE) {
      const { data, error } = await this.supabase
        .from('exchanges')
        .select('id, slug, name, status, website_url, country')
        .eq('status', 'active')
        .range(offset, offset + PAGE_SIZE - 1)

      if (error) {
        throw new Error(`Failed to fetch exchanges: ${error.message}`)
      }

      const batch = (data || []) as ExchangeRecord[]
      rows.push(...batch)

      if (batch.length < PAGE_SIZE) break
    }

    return rows
  }

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

  private async loadLatestCmcRankSnapshot(): Promise<Map<string, CmcMarketData>> {
    const { data: latestSnapshot, error: latestError } = await this.supabase
      .from('market_data_daily')
      .select('recorded_at')
      .eq('source', 'coinmarketcap')
      .gte('cmc_rank', 1)
      .lte('cmc_rank', 5000)
      .order('recorded_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (latestError) {
      throw new Error(`Failed to fetch latest CMC rank snapshot date: ${latestError.message}`)
    }

    if (!latestSnapshot?.recorded_at) {
      return new Map()
    }

    const marketDataByKey = new Map<string, CmcMarketData>()

    for (let offset = 0; ; offset += PAGE_SIZE) {
      const { data, error } = await this.supabase
        .from('market_data_daily')
        .select('slug, cmc_rank, market_cap')
        .eq('recorded_at', latestSnapshot.recorded_at)
        .eq('source', 'coinmarketcap')
        .gte('cmc_rank', 1)
        .lte('cmc_rank', 5000)
        .order('cmc_rank', { ascending: true, nullsFirst: false })
        .range(offset, offset + PAGE_SIZE - 1)

      if (error) {
        throw new Error(`Failed to fetch latest CMC ranks: ${error.message}`)
      }

      const batch = (data || []) as LatestCmcMarketDataRow[]
      for (const row of batch) {
        const slug = normalizeKey(row.slug)
        const rank = toNullableNumber(row.cmc_rank)
        if (slug && rank !== null) {
          marketDataByKey.set(slug, {
            cmcRank: rank,
            marketCap: toNullableNumber(row.market_cap),
          })
        }
      }

      if (batch.length < PAGE_SIZE) break
    }

    return marketDataByKey
  }

  private async loadLatestCmcRanksForKeys(keys: string[]): Promise<Map<string, CmcMarketData>> {
    const uniqueKeys = Array.from(new Set(keys.map(normalizeKey).filter(Boolean)))
    const marketDataByKey = new Map<string, CmcMarketData>()
    const chunkSize = 100

    for (let chunkStart = 0; chunkStart < uniqueKeys.length; chunkStart += chunkSize) {
      const chunk = uniqueKeys.slice(chunkStart, chunkStart + chunkSize)

      for (let offset = 0; ; offset += PAGE_SIZE) {
        const { data, error } = await this.supabase
          .from('market_data_daily')
          .select('slug, cmc_rank, market_cap')
          .eq('source', 'coinmarketcap')
          .in('slug', chunk)
          .gte('cmc_rank', 1)
          .lte('cmc_rank', 5000)
          .order('recorded_at', { ascending: false })
          .order('cmc_rank', { ascending: true, nullsFirst: false })
          .range(offset, offset + PAGE_SIZE - 1)

        if (error) {
          throw new Error(`Failed to fetch fallback CMC ranks: ${error.message}`)
        }

        const batch = (data || []) as LatestCmcMarketDataRow[]
        for (const row of batch) {
          const slug = normalizeKey(row.slug)
          const rank = toNullableNumber(row.cmc_rank)
          if (slug && rank !== null && !marketDataByKey.has(slug)) {
            marketDataByKey.set(slug, {
              cmcRank: rank,
              marketCap: toNullableNumber(row.market_cap),
            })
          }
        }

        if (chunk.every((key) => marketDataByKey.has(key)) || batch.length < PAGE_SIZE) break
      }
    }

    return marketDataByKey
  }

  private async loadLatestCmcRanksForListingRows(rows: ExchangeListingRecord[]): Promise<Map<string, CmcMarketData>> {
    const marketDataByKey = await this.loadLatestCmcRankSnapshot()
    const missingKeys = getMissingProjectMarketDataKeys(rows, marketDataByKey)
    if (missingKeys.length === 0) return marketDataByKey

    const fallbackMarketData = await this.loadLatestCmcRanksForKeys(missingKeys)
    for (const [key, marketData] of fallbackMarketData) {
      if (!marketDataByKey.has(key)) marketDataByKey.set(key, marketData)
    }

    return marketDataByKey
  }

  private async loadReportAvailabilityAliasCandidates(): Promise<ProjectReportAvailabilityCandidateWithStatus[]> {
    const rows: ProjectReportAvailabilityCandidateWithStatus[] = []

    for (let offset = 0; ; offset += PAGE_SIZE) {
      const { data, error } = await this.supabase
        .from('tracked_projects')
        .select('id, name, slug, symbol, coingecko_id, cmc_id, aliases, status')
        .in('status', ['active', 'monitoring_only'])
        .range(offset, offset + PAGE_SIZE - 1)

      if (error) {
        throw new Error(`Failed to fetch report availability alias candidates: ${error.message}`)
      }

      const batch = (data || []) as ProjectReportAvailabilityCandidateWithStatus[]
      rows.push(...batch)

      if (batch.length < PAGE_SIZE) break
    }

    return rows
  }

  async getExchangeAggregates() {
    const [exchanges, { rows }] = await Promise.all([
      this.loadActiveExchanges(),
      this.loadActiveListingRows(),
    ])
    const cmcRankByKey = await this.loadLatestCmcRanksForListingRows(rows)
    return buildExchangeAggregates({ exchanges, listings: applyLatestCmcRanks(rows, cmcRankByKey) })
  }

  async getExchangeProjects(exchangeKey: string, locale?: string) {
    const normalizedExchangeKey = normalizeKey(exchangeKey)
    const [exchanges, { rows }] = await Promise.all([
      this.loadActiveExchanges(),
      this.loadActiveListingRows(),
    ])
    const cmcRankByKey = await this.loadLatestCmcRanksForListingRows(rows)
    const rankedRows = applyLatestCmcRanks(rows, cmcRankByKey)
    const exchange = exchanges.find((candidate) => exchangeMatches(candidate, normalizedExchangeKey)) ?? null
    let result = buildExchangeProjectRows(rankedRows, normalizedExchangeKey)

    if (locale && result.projects.length > 0) {
      const listedProjectsById = new Map<string, ExchangeProjectRecord>()

      for (const row of rankedRows) {
        if (!isActiveListing(row)) continue

        const rowExchange = first(row.exchange)
        const project = first(row.project)
        if (rowExchange && project && exchangeMatches(rowExchange, normalizedExchangeKey)) {
          listedProjectsById.set(project.id, project)
        }
      }

      const aliasCandidates = await this.loadReportAvailabilityAliasCandidates()
      const listedProjects = Array.from(listedProjectsById.values())
      const listedProjectKeys = new Set(listedProjects.flatMap(getProjectReportAvailabilityKeys))
      const matchingAliasCandidates = aliasCandidates.filter((project) => (
        listedProjectsById.has(project.id)
        || getProjectReportAvailabilityKeys(project).some((key) => listedProjectKeys.has(key))
      ))
      let reportClient: SupabaseClient | undefined
      try {
        reportClient = createSupabaseAdminClient()
      } catch (error) {
        console.error('Using exchange listing client for report availability (admin key unavailable)', {
          message: error instanceof Error ? error.message : String(error),
        })
      }

      const listedProjectIds = Array.from(new Set([
        ...listedProjects.map((project) => project.id),
        ...matchingAliasCandidates.map((project) => project.id),
      ]))
      const visibleReports = await fetchVisibleReportsForProjectIds(listedProjectIds, reportClient, this.supabase)
      const availabilityByProjectId = visibleReports.loaded
        ? buildReportAvailabilityByProjectId(visibleReports.reports, locale)
        : undefined

      if (availabilityByProjectId) {
        applyProjectReportAvailabilityAliases(availabilityByProjectId, listedProjects, matchingAliasCandidates)
        result = buildExchangeProjectRows(rankedRows, normalizedExchangeKey, availabilityByProjectId)
      }
    }

    if (!result.exchange) {
      return {
        exchange,
        projects: [],
        ...calculateBceExchangeScore([]),
      }
    }

    const listedProjectsById = new Map<string, ExchangeProjectRecord>()
    for (const row of rankedRows) {
      if (!isActiveListing(row)) continue

      const rowExchange = first(row.exchange)
      const project = first(row.project)
      if (rowExchange && project && exchangeMatches(rowExchange, normalizedExchangeKey) && !listedProjectsById.has(project.id)) {
        listedProjectsById.set(project.id, project)
      }
    }

    return {
      ...result,
      ...calculateBceExchangeScore(Array.from(listedProjectsById.values())),
    }
  }
}

export function createExchangesRepository(supabase: SupabaseClient) {
  return new ExchangesRepository(supabase)
}
