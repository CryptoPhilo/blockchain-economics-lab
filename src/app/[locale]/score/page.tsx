import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import { createProjectsRepository } from '@/lib/repositories/projects'
import { pickLatestReport } from '@/lib/report-versioning'
import type { ProjectReport } from '@/lib/types'
import type { SupabaseClient } from '@supabase/supabase-js'
import ScoreTableGate from '@/components/ScoreTableGate'
import { fetchCMCTopListings } from '@/lib/coinmarketcap'
import { unstable_cache } from 'next/cache'

export const revalidate = 300

/**
 * CMC-Style Market Cap Ranking Page + Report Badges (BCE-379)
 *
 * Shows top 500 projects by market cap across 5 pages (100 per page).
 * Each row includes price, 24h change, market cap, BCE Score, and report badges.
 * Data: latest CMC market_data_daily snapshot, enriched by tracked_projects.
 */

const ITEMS_PER_PAGE = 100
const MAX_RANK = 500
const REPORT_AVAILABILITY_QUERY_CHUNK_SIZE = 80
const REPORT_AVAILABILITY_SLUG_QUERY_CHUNK_SIZE = 250
const SCOREBOARD_REPORT_QUERY_PAGE_SIZE = 1000
const SCOREBOARD_DATA_CACHE_SECONDS = 300
const SCORE_HEADER_BACKGROUND_IMAGE = '/images/score-header-bg.png'
export const MIN_CMC_CANONICAL_TOP_500_SNAPSHOT_ROWS = 500
const SCOREBOARD_ENGLISH_ASSET_FALLBACK_LOCALES = new Set(['de', 'es', 'fr'])
const SCOREBOARD_VISIBLE_REPORT_STATUSES = ['published', 'in_review'] as const
const SCOREBOARD_CANONICAL_ALIASES = [
  { alias: 'ethena-usde', slug: 'ethena' },
  { alias: 'usde', slug: 'ethena' },
  { alias: 'ether-fi-ethfi', slug: 'ether-fi' },
  { alias: 'optimism-ethereum', slug: 'optimism' },
  { alias: 'sei-network', slug: 'sei' },
  { alias: 'pancakeswap-token', slug: 'pancakeswap' },
  { alias: 'injective-protocol', slug: 'injective' },
  { alias: 'curve-dao-token', slug: 'curve-dao' },
  { alias: 'blockstack', slug: 'stacks' },
  { alias: 'fetch-ai', slug: 'artificial-superintelligence-alliance' },
  { alias: 'euro-coin', slug: 'eurc' },
  { alias: 'eur-coinvertible', slug: 'eur-coinvertible' },
  { alias: 'eur coinvertible', slug: 'eur-coinvertible' },
  { alias: 'eur coinvertible eurcv', slug: 'eur-coinvertible' },
  { alias: 'eurcv', slug: 'eur-coinvertible' },
  { alias: 'multi-collateral-dai', slug: 'dai' },
  { alias: 'world-liberty-financial-wlfi', slug: 'world-liberty-financial' },
  { alias: 'world-liberty-financial-usd', slug: 'usd1' },
  { alias: 'bnb', slug: 'binancecoin' },
  { alias: 'unus-sed-leo', slug: 'leo-token' },
  { alias: 'toncoin', slug: 'the-open-network' },
  { alias: 'hedera', slug: 'hedera-hashgraph' },
  { alias: 'pi', slug: 'pi-network' },
  { alias: 'worldcoin-org', slug: 'worldcoin' },
  { alias: 'gatetoken', slug: 'gate' },
  { alias: 'flare', slug: 'flare-networks' },
  { alias: 'genius-3', slug: 'genius-terminal' },
  { alias: 'ethgas', slug: 'eth-gas' },
  { alias: 'gwei', slug: 'eth-gas' },
  { alias: 'river-protocol', slug: 'river' },
  { alias: 'river', slug: 'river' },
  { alias: 'ab', slug: 'ab-chain' },
  { alias: 'starknet-token', slug: 'starknet' },
  { alias: 'nexpace', slug: 'maplestory-universe' },
  { alias: 'nxpc', slug: 'maplestory-universe' },
  { alias: 'msu', slug: 'maplestory-universe' },
  { alias: 'soon', slug: 'soon-network' },
] as const
const SCOREBOARD_CANONICAL_ALIAS_TARGET_SLUGS = Array.from(
  new Set(SCOREBOARD_CANONICAL_ALIASES.map(({ slug }) => slug)),
)
const SCOREBOARD_CANONICAL_ALIAS_TARGET_BY_ALIAS = new Map<string, string>(
  SCOREBOARD_CANONICAL_ALIASES.map(({ alias, slug }) => [alias, slug]),
)

type TrackedScoreboardProject = Awaited<
  ReturnType<ReturnType<typeof createProjectsRepository>['getProjectsForScoreboard']>
>[number]

type ScoreboardSnapshotRow = Awaited<
  ReturnType<ReturnType<typeof createProjectsRepository>['getLatestScoreboardMarketSnapshot']>
>[number]

type ReportTypeKey = 'econ' | 'maturity' | 'forensic'
type ReportAvailability = {
  reportTypes: string[]
  reportDates: Record<ReportTypeKey, string | null>
  maturityScore: number | null
  suppressedReportTypes?: ReportTypeKey[]
}
type ReportAvailabilityBuildOptions = {
  includeSuppressedReportTypes?: boolean
}

type ScoreboardVisibleReportRow = {
  project_id: string
  report_type: ReportTypeKey
  id?: string
  version?: number
  is_latest?: boolean | null
  status?: ProjectReport['status'] | null
  language?: ProjectReport['language'] | null
  published_at?: string | null
  updated_at?: string | null
  created_at?: string | null
  gdrive_urls_by_lang?: ProjectReport['gdrive_urls_by_lang']
  file_urls_by_lang?: ProjectReport['file_urls_by_lang']
  slide_html_urls_by_lang?: unknown
  card_data?: ProjectReport['card_data']
}

type ScoreboardVisibleReportRowWithProjectSlug = ScoreboardVisibleReportRow & {
  tracked_projects?: { slug?: string | null } | null
}

type ScoreboardReportQueryResult = {
  data?: unknown[] | null
  error?: { message?: string } | null
}

async function fetchScoreboardReportPages<T>(
  makeQuery: () => { range: (from: number, to: number) => PromiseLike<ScoreboardReportQueryResult> },
  errorContext: Record<string, unknown>,
): Promise<{ rows: T[]; loaded: boolean }> {
  const rows: T[] = []

  for (let start = 0; ; start += SCOREBOARD_REPORT_QUERY_PAGE_SIZE) {
    const { data, error } = await makeQuery().range(start, start + SCOREBOARD_REPORT_QUERY_PAGE_SIZE - 1)

    if (error) {
      console.error('Failed to fetch scoreboard report availability', {
        ...errorContext,
        message: error.message,
        rangeStart: start,
        rangeSize: SCOREBOARD_REPORT_QUERY_PAGE_SIZE,
      })
      return { rows: [], loaded: false }
    }

    const pageRows = (data || []) as T[]
    rows.push(...pageRows)
    if (pageRows.length < SCOREBOARD_REPORT_QUERY_PAGE_SIZE) {
      return { rows, loaded: true }
    }
  }
}

function normalizeKey(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim().toLowerCase()
  return normalized.length > 0 ? normalized : null
}

function normalizeIdentityKey(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/[’']/g, '')
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return normalized.length > 0 ? normalized : null
}

function toNumber(value: unknown): number {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function toCmcCanonicalRank(value: unknown): number | null {
  const rank = toNumber(value)
  return Number.isInteger(rank) && rank >= 1 && rank <= MAX_RANK ? rank : null
}

function getProjectLookupQuality(project: TrackedScoreboardProject) {
  let quality = 0
  if (project.last_econ_report_at) quality += 10
  if (project.last_maturity_report_at) quality += 10
  if (project.last_forensic_report_at) quality += 10
  if (project.maturity_score != null) quality += 5
  if (project.category) quality += 1
  return quality
}

function addProjectLookup(
  lookup: Map<string, TrackedScoreboardProject>,
  key: unknown,
  project: TrackedScoreboardProject,
  options: { overwrite?: boolean } = {}
) {
  const normalized = normalizeKey(key)
  if (!normalized) return
  const existing = lookup.get(normalized)
  if (
    options.overwrite
    || !existing
    || getProjectLookupQuality(project) > getProjectLookupQuality(existing)
  ) {
    lookup.set(normalized, project)
  }
}

export function buildTrackedProjectLookup(
  projects: TrackedScoreboardProject[],
  options: { includeProjectAliases?: boolean } = {},
) {
  const lookup = new Map<string, TrackedScoreboardProject>()
  const includeProjectAliases = options.includeProjectAliases ?? true

  for (const project of projects) {
    addProjectLookup(lookup, project.slug, project)
    addProjectLookup(lookup, project.coingecko_id, project)
    addProjectLookup(lookup, project.cmc_id, project)
    if (includeProjectAliases && Array.isArray(project.aliases)) {
      for (const alias of project.aliases) {
        addProjectLookup(lookup, alias, project, { overwrite: true })
      }
    }
  }

  for (const { alias, slug } of SCOREBOARD_CANONICAL_ALIASES) {
    const canonicalProject = lookup.get(slug)
    if (canonicalProject) {
      addProjectLookup(lookup, alias, canonicalProject, { overwrite: true })
    }
  }

  return lookup
}

export function buildTrackedProjectIdentityLookup(projects: TrackedScoreboardProject[]) {
  const byName = new Map<string, TrackedScoreboardProject>()
  const symbolCandidates = new Map<string, TrackedScoreboardProject | null>()

  for (const project of projects) {
    const nameKey = normalizeIdentityKey(project.name)
    if (nameKey && !byName.has(nameKey)) {
      byName.set(nameKey, project)
    }

    const symbolKey = normalizeIdentityKey(project.symbol)
    if (!symbolKey || symbolKey.length < 3) continue
    if (symbolCandidates.has(symbolKey)) {
      symbolCandidates.set(symbolKey, null)
    } else {
      symbolCandidates.set(symbolKey, project)
    }
  }

  const byUniqueSymbol = new Map<string, TrackedScoreboardProject>()
  for (const [symbol, project] of symbolCandidates) {
    if (project) byUniqueSymbol.set(symbol, project)
  }

  return { byName, byUniqueSymbol }
}

export function mergeScoreboardProjects(
  primaryProjects: TrackedScoreboardProject[],
  supplementalProjects: TrackedScoreboardProject[],
) {
  const merged = new Map<string, TrackedScoreboardProject>()

  for (const project of primaryProjects) {
    const key = project.id || project.slug
    if (key) merged.set(key, project)
  }

  for (const project of supplementalProjects) {
    const key = project.id || project.slug
    if (key && !merged.has(key)) merged.set(key, project)
  }

  return Array.from(merged.values())
}

function formatSnapshotName(slug: string) {
  return slug
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function formatSnapshotSymbol(slug: string) {
  return slug
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .slice(0, 6)
    .toUpperCase() || slug.slice(0, 6).toUpperCase()
}

function formatCmcIdentity(value: unknown) {
  if (typeof value !== 'string') return null
  const normalized = value.trim()
  return normalized.length > 0 ? normalized : null
}

function getSnapshotDisplayName(
  snapshot: ScoreboardSnapshotRow,
  project: TrackedScoreboardProject | undefined,
) {
  return formatCmcIdentity(snapshot.cmc_name) || project?.name || formatSnapshotName(snapshot.slug)
}

function getSnapshotDisplaySymbol(
  snapshot: ScoreboardSnapshotRow,
  project: TrackedScoreboardProject | undefined,
) {
  return formatCmcIdentity(snapshot.cmc_symbol) || project?.symbol || formatSnapshotSymbol(snapshot.slug)
}

function getReportTimestamp(report: {
  published_at?: string | null
  updated_at?: string | null
  created_at?: string | null
}) {
  return report.published_at || report.updated_at || report.created_at || null
}

function createFallbackReportAvailability(project: TrackedScoreboardProject | undefined): ReportAvailability {
  const reportTypes: string[] = []
  if (project?.last_econ_report_at) reportTypes.push('econ')
  if (project?.last_maturity_report_at) reportTypes.push('maturity')
  if (project?.last_forensic_report_at) reportTypes.push('forensic')
  return {
    reportTypes,
    reportDates: {
      econ: project?.last_econ_report_at ?? null,
      maturity: project?.last_maturity_report_at ?? null,
      forensic: project?.last_forensic_report_at ?? null,
    },
    maturityScore: project?.maturity_score == null ? null : toNumber(project.maturity_score),
  }
}

function createEmptyReportAvailability(): ReportAvailability {
  return {
    reportTypes: [],
    reportDates: { econ: null, maturity: null, forensic: null },
    maturityScore: null,
  }
}

function addSuppressedReportType(
  availability: ReportAvailability,
  reportType: ReportTypeKey,
) {
  const suppressedReportTypes = availability.suppressedReportTypes ?? []
  if (!suppressedReportTypes.includes(reportType)) {
    availability.suppressedReportTypes = [...suppressedReportTypes, reportType]
  }
}

function addSuppressedReportTypeToMap(
  map: Map<string, ReportAvailability>,
  key: string,
  reportType: ReportTypeKey,
) {
  const existing = map.get(key) ?? createEmptyReportAvailability()
  addSuppressedReportType(existing, reportType)
  map.set(key, existing)
}

function mergeNonForensicFallback(
  source: ReportAvailability,
  fallback: ReportAvailability,
): ReportAvailability {
  const merged: ReportAvailability = {
    reportTypes: [...source.reportTypes],
    reportDates: { ...source.reportDates },
    maturityScore: source.maturityScore ?? fallback.maturityScore,
    suppressedReportTypes: source.suppressedReportTypes,
  }

  for (const reportType of ['econ', 'maturity'] as const) {
    if (source.suppressedReportTypes?.includes(reportType)) continue
    if (!fallback.reportTypes.includes(reportType)) continue
    if (!merged.reportTypes.includes(reportType)) {
      merged.reportTypes.push(reportType)
    }

    const fallbackDate = fallback.reportDates[reportType]
    const currentDate = merged.reportDates[reportType]
    if (fallbackDate && (!currentDate || new Date(fallbackDate).getTime() > new Date(currentDate).getTime())) {
      merged.reportDates[reportType] = fallbackDate
    }
  }

  return merged
}

function getReportAvailability(
  project: TrackedScoreboardProject | undefined,
  availabilityByProjectId?: Map<string, ReportAvailability>,
  canonicalAvailability?: ReportAvailability,
): ReportAvailability {
  const fallback = createFallbackReportAvailability(project)
  if (canonicalAvailability) return mergeNonForensicFallback(canonicalAvailability, fallback)
  const live = project?.id ? availabilityByProjectId?.get(project.id) : undefined
  if (!availabilityByProjectId) return fallback
  if (!live) {
    return createEmptyReportAvailability()
  }

  return mergeNonForensicFallback(live, fallback)
}

function hasNonEmptyAssetValue(value: unknown): boolean {
  if (typeof value === 'string') {
    return value.trim().length > 0
  }

  if (Array.isArray(value)) {
    return value.some(hasNonEmptyAssetValue)
  }

  return false
}

function hasUrlAssetEntry(value: unknown): boolean {
  if (typeof value === 'string') {
    return value.trim().length > 0
  }

  if (!value || typeof value !== 'object') {
    return false
  }

  const entry = value as { url?: unknown; download_url?: unknown }
  return hasNonEmptyAssetValue(entry.url) || hasNonEmptyAssetValue(entry.download_url)
}

function hasScoreboardAssetForLocale(report: ScoreboardVisibleReportRow, locale: string): boolean {
  if (!locale) return true

  const gdriveUrls = report.gdrive_urls_by_lang as Record<string, unknown> | undefined
  const fileUrls = report.file_urls_by_lang as Record<string, unknown> | undefined
  const slideUrls = report.slide_html_urls_by_lang as Record<string, unknown> | undefined

  return hasUrlAssetEntry(gdriveUrls?.[locale])
    || hasUrlAssetEntry(fileUrls?.[locale])
    || hasNonEmptyAssetValue(slideUrls?.[locale])
}

function reportLanguageMatchesScoreboardLocale(report: ScoreboardVisibleReportRow, locale: string): boolean {
  const normalizedLocale = normalizeKey(locale)
  const reportLanguage = normalizeKey(report.language)
  if (!normalizedLocale || !reportLanguage) return true
  if (reportLanguage === normalizedLocale) return true
  return SCOREBOARD_ENGLISH_ASSET_FALLBACK_LOCALES.has(normalizedLocale) && reportLanguage === 'en'
}

function reportIsVisibleOnScoreboard(report: ScoreboardVisibleReportRow, locale: string): boolean {
  const normalizedLocale = normalizeKey(locale) ?? locale
  if (
    report.status
    && !SCOREBOARD_VISIBLE_REPORT_STATUSES.includes(
      report.status as (typeof SCOREBOARD_VISIBLE_REPORT_STATUSES)[number],
    )
  ) return false
  if (!reportLanguageMatchesScoreboardLocale(report, normalizedLocale)) return false
  return hasScoreboardAssetForLocale(report, normalizedLocale)
    || (SCOREBOARD_ENGLISH_ASSET_FALLBACK_LOCALES.has(normalizedLocale) && hasScoreboardAssetForLocale(report, 'en'))
}

function extractReportMaturityScore(report: ScoreboardVisibleReportRow): number | null {
  if (report.report_type !== 'maturity') return null
  const cardData = report.card_data as Record<string, unknown> | null | undefined
  const rawScore = cardData?.maturity_score ?? cardData?.score
  if (rawScore == null) return null
  const score = toNumber(rawScore)
  return Number.isFinite(score) ? score : null
}

function getCanonicalScoreboardTargetSlug(...values: unknown[]) {
  for (const value of values) {
    const normalized = normalizeKey(value)
    const targetSlug = normalized ? SCOREBOARD_CANONICAL_ALIAS_TARGET_BY_ALIAS.get(normalized) : undefined
    if (targetSlug) return targetSlug
  }
  return undefined
}

function findTrackedProjectForSnapshot(
  snapshot: ScoreboardSnapshotRow,
  trackedLookup: Map<string, TrackedScoreboardProject>,
  identityLookup?: ReturnType<typeof buildTrackedProjectIdentityLookup>,
) {
  const snapshotSlug = normalizeKey(snapshot.slug) || ''
  const canonicalTargetSlug = getCanonicalScoreboardTargetSlug(
    snapshotSlug,
    snapshot.cmc_name,
    snapshot.cmc_symbol,
  )
  const canonicalProject = canonicalTargetSlug ? trackedLookup.get(canonicalTargetSlug) : undefined
  if (canonicalProject) return canonicalProject

  const directProject = trackedLookup.get(snapshotSlug)
  if (directProject) return directProject

  const cmcNameKey = normalizeIdentityKey(snapshot.cmc_name)
  if (cmcNameKey) {
    const nameProject = identityLookup?.byName.get(cmcNameKey)
    if (nameProject) return nameProject
  }

  const cmcSymbolKey = normalizeIdentityKey(snapshot.cmc_symbol)
  if (cmcSymbolKey) {
    return identityLookup?.byUniqueSymbol.get(cmcSymbolKey)
  }

  return undefined
}

export function buildReportAvailabilityByProjectId(
  reports: ScoreboardVisibleReportRow[],
  locale: string,
  options: ReportAvailabilityBuildOptions = {},
) {
  const map = new Map<string, ReportAvailability>()
  const latestByProjectType = new Map<string, ScoreboardVisibleReportRow>()

  for (const report of reports) {
    if (!report.project_id) continue
    if (!reportIsVisibleOnScoreboard(report, locale)) {
      if (options.includeSuppressedReportTypes) {
        addSuppressedReportTypeToMap(map, report.project_id, report.report_type)
      }
      continue
    }
    const key = `${report.project_id}:${report.report_type}`
    const latest = pickLatestReport([latestByProjectType.get(key), report].filter(Boolean) as ScoreboardVisibleReportRow[])
    if (latest) latestByProjectType.set(key, latest)
  }

  for (const report of latestByProjectType.values()) {
    const existing = map.get(report.project_id) ?? createEmptyReportAvailability()

    if (!existing.reportTypes.includes(report.report_type)) {
      existing.reportTypes.push(report.report_type)
    }

    const timestamp = getReportTimestamp(report)
    const current = existing.reportDates[report.report_type]
    if (timestamp && (!current || new Date(timestamp).getTime() > new Date(current).getTime())) {
      existing.reportDates[report.report_type] = timestamp
    }

    const reportMaturityScore = extractReportMaturityScore(report)
    if (reportMaturityScore != null) {
      existing.maturityScore = reportMaturityScore
    }

    map.set(report.project_id, existing)
  }

  return map
}

export function buildReportAvailabilityByProjectSlug(
  reports: ScoreboardVisibleReportRowWithProjectSlug[],
  locale: string,
  options: ReportAvailabilityBuildOptions = {},
) {
  const map = new Map<string, ReportAvailability>()
  const latestByProjectType = new Map<string, ScoreboardVisibleReportRowWithProjectSlug>()

  for (const report of reports) {
    const cardData = report.card_data as Record<string, unknown> | null | undefined
    const slug = normalizeKey(report.tracked_projects?.slug) ?? normalizeKey(cardData?.slug)
    if (!slug) continue
    if (!reportIsVisibleOnScoreboard(report, locale)) {
      if (options.includeSuppressedReportTypes) {
        addSuppressedReportTypeToMap(map, slug, report.report_type)
      }
      continue
    }
    const key = `${slug}:${report.report_type}`
    const latest = pickLatestReport(
      [latestByProjectType.get(key), report].filter(Boolean) as ScoreboardVisibleReportRowWithProjectSlug[],
    )
    if (latest) latestByProjectType.set(key, latest)
  }

  for (const report of latestByProjectType.values()) {
    const cardData = report.card_data as Record<string, unknown> | null | undefined
    const slug = normalizeKey(report.tracked_projects?.slug) ?? normalizeKey(cardData?.slug)
    if (!slug) continue
    const existing = map.get(slug) ?? createEmptyReportAvailability()

    if (!existing.reportTypes.includes(report.report_type)) {
      existing.reportTypes.push(report.report_type)
    }

    const timestamp = getReportTimestamp(report)
    const current = existing.reportDates[report.report_type]
    if (timestamp && (!current || new Date(timestamp).getTime() > new Date(current).getTime())) {
      existing.reportDates[report.report_type] = timestamp
    }

    const reportMaturityScore = extractReportMaturityScore(report)
    if (reportMaturityScore != null) {
      existing.maturityScore = reportMaturityScore
    }

    map.set(slug, existing)
  }

  return map
}

export async function fetchVisibleReportsForScoreboard(
  projectIds: string[],
  reportSupabase?: SupabaseClient,
): Promise<{ reports: ScoreboardVisibleReportRow[]; loaded: boolean }> {
  if (projectIds.length === 0) {
    return { reports: [], loaded: true }
  }

  const supabase = reportSupabase ?? createSupabaseAdminClient()
  const reports: ScoreboardVisibleReportRow[] = []

  for (let index = 0; index < projectIds.length; index += REPORT_AVAILABILITY_QUERY_CHUNK_SIZE) {
    const chunk = projectIds.slice(index, index + REPORT_AVAILABILITY_QUERY_CHUNK_SIZE)
    const result = await fetchScoreboardReportPages<ScoreboardVisibleReportRow>(
      () => supabase
        .from('project_reports')
        .select([
          'project_id',
          'id',
          'report_type',
          'version',
          'is_latest',
          'status',
          'language',
          'published_at',
          'updated_at',
          'created_at',
          'gdrive_urls_by_lang',
          'file_urls_by_lang',
          'slide_html_urls_by_lang',
          'card_data',
        ].join(', '))
        .in('project_id', chunk)
        .in('report_type', ['econ', 'maturity', 'forensic'])
        .in('status', SCOREBOARD_VISIBLE_REPORT_STATUSES),
      {
        chunkStart: index,
        chunkSize: chunk.length,
      },
    )
    if (!result.loaded) {
      return { reports: [], loaded: false }
    }

    reports.push(...result.rows)
  }

  return { reports, loaded: true }
}

export async function fetchVisibleReportsForScoreboardByProjectSlugs(
  projectSlugs: string[],
  reportSupabase?: SupabaseClient,
): Promise<{ reports: ScoreboardVisibleReportRowWithProjectSlug[]; loaded: boolean }> {
  const normalizedSlugs = Array.from(new Set(projectSlugs.map(normalizeKey).filter(Boolean) as string[]))
  if (normalizedSlugs.length === 0) {
    return { reports: [], loaded: true }
  }

  const supabase = reportSupabase ?? createSupabaseAdminClient()
  const reports: ScoreboardVisibleReportRowWithProjectSlug[] = []
  const seenReportIds = new Set<string>()
  const pushReports = (rows: ScoreboardVisibleReportRowWithProjectSlug[]) => {
    for (const row of rows) {
      const id = typeof row.id === 'string' ? row.id : ''
      if (id) {
        if (seenReportIds.has(id)) continue
        seenReportIds.add(id)
      }
      reports.push(row)
    }
  }

  for (let index = 0; index < normalizedSlugs.length; index += REPORT_AVAILABILITY_SLUG_QUERY_CHUNK_SIZE) {
    const chunk = normalizedSlugs.slice(index, index + REPORT_AVAILABILITY_SLUG_QUERY_CHUNK_SIZE)
    const slugResult = await fetchScoreboardReportPages<ScoreboardVisibleReportRowWithProjectSlug>(
      () => supabase
        .from('project_reports')
        .select([
          'project_id',
          'id',
          'report_type',
          'version',
          'is_latest',
          'status',
          'language',
          'published_at',
          'updated_at',
          'created_at',
          'gdrive_urls_by_lang',
          'file_urls_by_lang',
          'slide_html_urls_by_lang',
          'card_data',
          'tracked_projects!inner(slug)',
        ].join(', '))
        .in('tracked_projects.slug', chunk)
        .in('report_type', ['econ', 'maturity', 'forensic'])
        .in('status', SCOREBOARD_VISIBLE_REPORT_STATUSES),
      {
        query: 'tracked_projects.slug',
        chunkStart: index,
        chunkSize: chunk.length,
      },
    )
    if (!slugResult.loaded) {
      return { reports: [], loaded: false }
    }

    pushReports(slugResult.rows)

    const cardSlugResult = await fetchScoreboardReportPages<ScoreboardVisibleReportRowWithProjectSlug>(
      () => supabase
        .from('project_reports')
        .select([
          'project_id',
          'id',
          'report_type',
          'version',
          'is_latest',
          'status',
          'language',
          'published_at',
          'updated_at',
          'created_at',
          'gdrive_urls_by_lang',
          'file_urls_by_lang',
          'slide_html_urls_by_lang',
          'card_data',
          'tracked_projects(slug)',
        ].join(', '))
        .in('card_data->>slug', chunk)
        .in('report_type', ['econ', 'maturity', 'forensic'])
        .in('status', SCOREBOARD_VISIBLE_REPORT_STATUSES),
      {
        query: 'card_data->>slug',
        chunkStart: index,
        chunkSize: chunk.length,
      },
    )
    if (!cardSlugResult.loaded) {
      return { reports: [], loaded: false }
    }

    pushReports(cardSlugResult.rows)
  }

  return { reports, loaded: true }
}

export async function fetchScoreboardCanonicalAliasTargetProjects(
  reportSupabase?: SupabaseClient,
): Promise<TrackedScoreboardProject[]> {
  if (SCOREBOARD_CANONICAL_ALIAS_TARGET_SLUGS.length === 0) return []

  const supabase = reportSupabase ?? createSupabaseAdminClient()
  const { data, error } = await supabase
    .from('tracked_projects')
    .select(`
      id, name, slug, symbol, category,
      market_cap_usd, coingecko_id, cmc_id, aliases, maturity_score,
      last_econ_report_at, last_maturity_report_at, last_forensic_report_at
    `)
    .in('slug', SCOREBOARD_CANONICAL_ALIAS_TARGET_SLUGS)

  if (error) {
    console.error('Failed to fetch scoreboard canonical alias target projects', {
      message: error.message,
    })
    return []
  }

  return (data || []) as TrackedScoreboardProject[]
}

async function fetchScoreboardSourceData() {
  const supabase = createSupabaseAdminClient()
  const projectsRepository = createProjectsRepository(supabase)

  const [baseTrackedProjects, cmcSnapshotRows, canonicalAliasTargetProjects] = await Promise.all([
    projectsRepository.getProjectsForScoreboard(),
    projectsRepository.getLatestScoreboardMarketSnapshot(MAX_RANK),
    fetchScoreboardCanonicalAliasTargetProjects(supabase),
  ])
  const scoreSnapshotRows = cmcSnapshotRows.length > 0
    ? cmcSnapshotRows
    : await fetchCMCTopListings(MAX_RANK).then((listings) => listings.map((listing) => ({
        slug: listing.slug,
        price_usd: listing.price_usd,
        market_cap: listing.market_cap,
        change_24h: listing.change_24h,
        recorded_at: listing.recorded_at,
        cmc_rank: listing.cmc_rank,
        cmc_symbol: listing.symbol,
        cmc_name: listing.name,
      })))

  return {
    scoreSnapshotRows,
    trackedProjects: mergeScoreboardProjects(baseTrackedProjects, canonicalAliasTargetProjects),
  }
}

const getCachedScoreboardSourceData = unstable_cache(
  fetchScoreboardSourceData,
  ['scoreboard-source-data-v1'],
  {
    revalidate: SCOREBOARD_DATA_CACHE_SECONDS,
    tags: ['scoreboard-source-data'],
  },
)

const getCachedVisibleReportsForScoreboardByProjectSlugs = unstable_cache(
  async (projectSlugs: string[]) => fetchVisibleReportsForScoreboardByProjectSlugs(projectSlugs),
  ['scoreboard-visible-reports-by-slugs-v1'],
  {
    revalidate: SCOREBOARD_DATA_CACHE_SECONDS,
    tags: ['scoreboard-visible-reports'],
  },
)

export function snapshotRowsToScoreRows(
  snapshotRows: ScoreboardSnapshotRow[],
  trackedLookup: Map<string, TrackedScoreboardProject>,
  availabilityByProjectId?: Map<string, ReportAvailability>,
  availabilityByProjectSlug?: Map<string, ReportAvailability>,
  identityLookup?: ReturnType<typeof buildTrackedProjectIdentityLookup>,
) {
  return snapshotRows
    .slice(0, MAX_RANK)
    .map((snapshot, index) => {
      const snapshotSlug = normalizeKey(snapshot.slug) || ''
      const canonicalTargetSlug = getCanonicalScoreboardTargetSlug(
        snapshotSlug,
        snapshot.cmc_name,
        snapshot.cmc_symbol,
      )
      const project = findTrackedProjectForSnapshot(snapshot, trackedLookup, identityLookup)
      const projectSlug = normalizeKey(project?.slug)
      const slugAvailability = canonicalTargetSlug
        ? availabilityByProjectSlug?.get(canonicalTargetSlug)
        : (projectSlug ? availabilityByProjectSlug?.get(projectSlug) : undefined)
          ?? availabilityByProjectSlug?.get(snapshotSlug)
      const reportAvailability = getReportAvailability(project, availabilityByProjectId, slugAvailability)

      const cmcRank = toCmcCanonicalRank(snapshot.cmc_rank)

      return {
        rank: cmcRank ?? index + 1,
        cmcRank,
        name: getSnapshotDisplayName(snapshot, project),
        symbol: getSnapshotDisplaySymbol(snapshot, project),
        slug: canonicalTargetSlug || project?.slug || snapshot.slug,
        change24h: snapshot.change_24h == null ? null : toNumber(snapshot.change_24h),
        marketCap: toNumber(snapshot.market_cap),
        score: project?.maturity_score == null ? reportAvailability.maturityScore : toNumber(project.maturity_score),
        category: project?.category || '',
        reportTypes: reportAvailability.reportTypes,
        reportDates: reportAvailability.reportDates,
      }
    })
}

export function canonicalSnapshotRowsToScoreRows(
  snapshotRows: ScoreboardSnapshotRow[],
  trackedProjects: TrackedScoreboardProject[],
  availabilityByProjectId?: Map<string, ReportAvailability>,
  availabilityByProjectSlug?: Map<string, ReportAvailability>,
) {
  const canonicalRows = getCanonicalScoreboardSnapshotRows(snapshotRows)

  if (!hasCompleteCmcCanonicalTop500Snapshot(canonicalRows)) return []
  return snapshotRowsToScoreRows(
    canonicalRows,
    buildTrackedProjectLookup(trackedProjects, { includeProjectAliases: false }),
    availabilityByProjectId,
    availabilityByProjectSlug,
    buildTrackedProjectIdentityLookup(trackedProjects),
  )
}

export function getCanonicalScoreboardSnapshotRows(snapshotRows: ScoreboardSnapshotRow[]) {
  return snapshotRows
    .filter((row) => toCmcCanonicalRank(row.cmc_rank) !== null)
    .sort((a, b) => (toCmcCanonicalRank(a.cmc_rank) ?? 0) - (toCmcCanonicalRank(b.cmc_rank) ?? 0))
}

export function getScoreboardReportScope(
  snapshotRows: ScoreboardSnapshotRow[],
  trackedProjects: TrackedScoreboardProject[],
  options: { requireCompleteCanonicalSnapshot?: boolean } = {},
) {
  const canonicalRows = getCanonicalScoreboardSnapshotRows(snapshotRows)

  if (options.requireCompleteCanonicalSnapshot !== false && !hasCompleteCmcCanonicalTop500Snapshot(canonicalRows)) {
    return { projectIds: [] as string[], projectSlugs: [] as string[] }
  }

  const trackedLookup = buildTrackedProjectLookup(trackedProjects, { includeProjectAliases: false })
  const identityLookup = buildTrackedProjectIdentityLookup(trackedProjects)
  const projectIds = new Set<string>()
  const projectSlugs = new Set<string>(SCOREBOARD_CANONICAL_ALIAS_TARGET_SLUGS)

  for (const snapshot of canonicalRows) {
    const snapshotSlug = normalizeKey(snapshot.slug) || ''
    const canonicalTargetSlug = getCanonicalScoreboardTargetSlug(
      snapshotSlug,
      snapshot.cmc_name,
      snapshot.cmc_symbol,
    )
    const project = findTrackedProjectForSnapshot(snapshot, trackedLookup, identityLookup)
    if (project?.id) projectIds.add(project.id)

    const projectSlug = normalizeKey(project?.slug)
    const reportSlug = canonicalTargetSlug || projectSlug || snapshotSlug
    if (reportSlug) projectSlugs.add(reportSlug)
  }

  return {
    projectIds: Array.from(projectIds),
    projectSlugs: Array.from(projectSlugs),
  }
}

export function hasCompleteCmcCanonicalTop500Snapshot(snapshotRows: ScoreboardSnapshotRow[]) {
  if (snapshotRows.length !== MIN_CMC_CANONICAL_TOP_500_SNAPSHOT_ROWS) return false

  const ranks = new Set(snapshotRows.map((row) => toCmcCanonicalRank(row.cmc_rank)))
  if (ranks.has(null) || ranks.size !== MIN_CMC_CANONICAL_TOP_500_SNAPSHOT_ROWS) return false

  for (let rank = 1; rank <= MAX_RANK; rank += 1) {
    if (!ranks.has(rank)) return false
  }

  return true
}

export default async function ScorePage({
  params,
  searchParams
}: {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ page?: string }>
}) {
  const { locale } = await params
  const { page: pageStr } = await searchParams

  const currentPage = Math.max(1, Math.min(5, parseInt(pageStr || '1', 10)))

  const { scoreSnapshotRows, trackedProjects } = await getCachedScoreboardSourceData()
  const canonicalScoreSnapshotRows = getCanonicalScoreboardSnapshotRows(scoreSnapshotRows)
  const hasCanonicalScoreSnapshot = hasCompleteCmcCanonicalTop500Snapshot(canonicalScoreSnapshotRows)

  // Paginate before report availability lookup so page 1 does not load badges for all 500 rows.
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE
  const pageSnapshotRows = hasCanonicalScoreSnapshot
    ? canonicalScoreSnapshotRows.slice(startIdx, startIdx + ITEMS_PER_PAGE)
    : []
  const reportScope = getScoreboardReportScope(pageSnapshotRows, trackedProjects, {
    requireCompleteCanonicalSnapshot: false,
  })
  let canonicalAliasReportResult: Awaited<ReturnType<typeof fetchVisibleReportsForScoreboardByProjectSlugs>>
  try {
    canonicalAliasReportResult = await getCachedVisibleReportsForScoreboardByProjectSlugs(reportScope.projectSlugs)
  } catch (error) {
    console.error('Failed to initialize scoreboard report availability boundary', {
      message: error instanceof Error ? error.message : String(error),
    })
    canonicalAliasReportResult = { reports: [], loaded: false }
  }
  const reportAvailabilityByProjectSlug = canonicalAliasReportResult.loaded
    ? buildReportAvailabilityByProjectSlug(canonicalAliasReportResult.reports, locale, {
      includeSuppressedReportTypes: true,
    })
    : undefined

  const rows = snapshotRowsToScoreRows(
    pageSnapshotRows,
    buildTrackedProjectLookup(trackedProjects, { includeProjectAliases: false }),
    canonicalAliasReportResult.loaded ? new Map() : undefined,
    reportAvailabilityByProjectSlug,
    buildTrackedProjectIdentityLookup(trackedProjects),
  )
  const totalPages = Math.ceil(Math.min(canonicalScoreSnapshotRows.length, MAX_RANK) / ITEMS_PER_PAGE)

  const isKo = locale === 'ko'

  return (
    <div className="max-w-6xl mx-auto px-6 pb-8 pt-6">
      {/* Header */}
      <section
        className="relative mb-4 overflow-hidden rounded-lg border border-white/10 bg-slate-950 bg-cover bg-center px-5 py-7 text-center shadow-xl shadow-black/25 sm:px-8 sm:py-9"
        style={{
          backgroundImage: `linear-gradient(180deg, rgba(3, 7, 18, 0.46), rgba(3, 7, 18, 0.78)), url(${SCORE_HEADER_BACKGROUND_IMAGE})`,
        }}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.08),transparent_38%)]" />
        <div className="relative mx-auto max-w-2xl">
          <h1 className="mb-2 text-3xl font-bold text-white drop-shadow-[0_2px_18px_rgba(0,0,0,0.85)] sm:text-4xl">
            {isKo ? '리포트' : 'Report'}
          </h1>
          <p className="mx-auto max-w-xl text-sm font-medium leading-6 text-slate-200 drop-shadow-[0_2px_14px_rgba(0,0,0,0.8)] sm:text-base">
            {isKo
              ? '시가총액 500위 종목들의 BCE 보고서를 확인하세요'
              : 'Crypto project rankings by market cap with BCE analysis reports'}
          </p>
        </div>
      </section>

      {/* Market cap ranking table with email gate */}
      {rows.length > 0 ? (
        <ScoreTableGate
          rows={rows}
          freeLimit={500}
          locale={locale}
          currentPage={currentPage}
          totalPages={totalPages}
          className="h-[clamp(720px,78dvh,880px)] overflow-auto pr-1"
        />
      ) : (
        <div className="text-center py-20">
          <p className="text-gray-500 text-lg">
            {isKo ? '아직 프로젝트 데이터가 없습니다.' : 'No project data available yet.'}
          </p>
          <p className="text-gray-600 text-sm mt-2">
            {isKo ? '프로젝트가 등록되면 여기에 표시됩니다.' : 'Rankings will appear here once projects are tracked.'}
          </p>
        </div>
      )}
    </div>
  )
}
