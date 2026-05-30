import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import { createProjectsRepository } from '@/lib/repositories/projects'
import { reportSupportsLocale } from '@/lib/report-locale'
import { pickLatestReport } from '@/lib/report-versioning'
import type { ProjectReport } from '@/lib/types'
import type { SupabaseClient } from '@supabase/supabase-js'
import ScoreTableGate from '@/components/ScoreTableGate'
import SubscribeForm from '@/components/SubscribeForm'

export const dynamic = 'force-dynamic'
export const revalidate = 0

/**
 * CMC-Style Market Cap Ranking Page + Report Badges (BCE-379)
 *
 * Shows top 200 projects by market cap across 2 pages (100 per page).
 * Each row includes price, 24h change, market cap, BCE Score, and report badges.
 * Data: latest CMC market_data_daily snapshot, enriched by tracked_projects.
 */

const ITEMS_PER_PAGE = 100
const MAX_RANK = 200
const REPORT_AVAILABILITY_QUERY_CHUNK_SIZE = 80
export const MIN_CMC_CANONICAL_TOP_200_SNAPSHOT_ROWS = 200
const SCOREBOARD_CANONICAL_ALIASES = [
  { alias: 'ethena-usde', slug: 'ethena' },
  { alias: 'usde', slug: 'ethena' },
  { alias: 'sei-network', slug: 'sei' },
  { alias: 'pancakeswap-token', slug: 'pancakeswap' },
  { alias: 'injective-protocol', slug: 'injective' },
  { alias: 'curve-dao-token', slug: 'curve-dao' },
  { alias: 'blockstack', slug: 'stacks' },
  { alias: 'fetch-ai', slug: 'artificial-superintelligence-alliance' },
  { alias: 'euro-coin', slug: 'eurc' },
  { alias: 'world-liberty-financial-wlfi', slug: 'world-liberty-financial' },
  { alias: 'genius-3', slug: 'genius-terminal' },
  { alias: 'ethgas', slug: 'eth-gas' },
  { alias: 'gwei', slug: 'eth-gas' },
  { alias: 'river-protocol', slug: 'river' },
  { alias: 'river', slug: 'river' },
  { alias: 'ab', slug: 'ab-chain' },
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
}

type ScoreboardVisibleReportRow = {
  project_id: string
  report_type: ReportTypeKey
  id?: string
  version?: number
  is_latest?: boolean | null
  language?: ProjectReport['language'] | null
  published_at?: string | null
  updated_at?: string | null
  created_at?: string | null
  gdrive_urls_by_lang?: ProjectReport['gdrive_urls_by_lang']
  file_urls_by_lang?: ProjectReport['file_urls_by_lang']
  slide_html_urls_by_lang?: unknown
}

type ScoreboardVisibleReportRowWithProjectSlug = ScoreboardVisibleReportRow & {
  tracked_projects?: { slug?: string | null } | null
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

function addProjectLookup(
  lookup: Map<string, TrackedScoreboardProject>,
  key: unknown,
  project: TrackedScoreboardProject,
  options: { overwrite?: boolean } = {}
) {
  const normalized = normalizeKey(key)
  if (normalized && (options.overwrite || !lookup.has(normalized))) {
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
  }
}

function getReportAvailability(
  project: TrackedScoreboardProject | undefined,
  availabilityByProjectId?: Map<string, ReportAvailability>,
  canonicalAvailability?: ReportAvailability,
): ReportAvailability {
  const fallback = createFallbackReportAvailability(project)
  if (canonicalAvailability) return canonicalAvailability
  const live = project?.id ? availabilityByProjectId?.get(project.id) : undefined
  if (!availabilityByProjectId) return fallback
  if (!live) {
    return {
      reportTypes: [],
      reportDates: { econ: null, maturity: null, forensic: null },
    }
  }

  const reportTypes = live.reportTypes
  return {
    reportTypes,
    reportDates: {
      econ: live.reportDates.econ,
      maturity: live.reportDates.maturity,
      forensic: live.reportDates.forensic,
    },
  }
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
) {
  const map = new Map<string, ReportAvailability>()
  const latestByProjectType = new Map<string, ScoreboardVisibleReportRow>()

  for (const report of reports) {
    if (!report.project_id) continue
    if (!reportSupportsLocale(report as ProjectReport, locale)) continue
    const key = `${report.project_id}:${report.report_type}`
    const latest = pickLatestReport([latestByProjectType.get(key), report].filter(Boolean) as ScoreboardVisibleReportRow[])
    if (latest) latestByProjectType.set(key, latest)
  }

  for (const report of latestByProjectType.values()) {
    const existing = map.get(report.project_id) ?? {
      reportTypes: [],
      reportDates: { econ: null, maturity: null, forensic: null },
    }

    if (!existing.reportTypes.includes(report.report_type)) {
      existing.reportTypes.push(report.report_type)
    }

    const timestamp = getReportTimestamp(report)
    const current = existing.reportDates[report.report_type]
    if (timestamp && (!current || new Date(timestamp).getTime() > new Date(current).getTime())) {
      existing.reportDates[report.report_type] = timestamp
    }

    map.set(report.project_id, existing)
  }

  return map
}

export function buildReportAvailabilityByProjectSlug(
  reports: ScoreboardVisibleReportRowWithProjectSlug[],
  locale: string,
) {
  const map = new Map<string, ReportAvailability>()
  const latestByProjectType = new Map<string, ScoreboardVisibleReportRowWithProjectSlug>()

  for (const report of reports) {
    const slug = normalizeKey(report.tracked_projects?.slug)
    if (!slug) continue
    if (!reportSupportsLocale(report as ProjectReport, locale)) continue
    const key = `${slug}:${report.report_type}`
    const latest = pickLatestReport(
      [latestByProjectType.get(key), report].filter(Boolean) as ScoreboardVisibleReportRowWithProjectSlug[],
    )
    if (latest) latestByProjectType.set(key, latest)
  }

  for (const report of latestByProjectType.values()) {
    const slug = normalizeKey(report.tracked_projects?.slug)
    if (!slug) continue
    const existing = map.get(slug) ?? {
      reportTypes: [],
      reportDates: { econ: null, maturity: null, forensic: null },
    }

    if (!existing.reportTypes.includes(report.report_type)) {
      existing.reportTypes.push(report.report_type)
    }

    const timestamp = getReportTimestamp(report)
    const current = existing.reportDates[report.report_type]
    if (timestamp && (!current || new Date(timestamp).getTime() > new Date(current).getTime())) {
      existing.reportDates[report.report_type] = timestamp
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
    const { data, error } = await supabase
      .from('project_reports')
      .select([
        'project_id',
        'id',
        'report_type',
        'version',
        'is_latest',
        'language',
        'published_at',
        'updated_at',
        'created_at',
        'gdrive_urls_by_lang',
        'file_urls_by_lang',
        'slide_html_urls_by_lang',
      ].join(', '))
      .in('project_id', chunk)
      .in('report_type', ['econ', 'maturity', 'forensic'])
      .in('status', ['published', 'coming_soon', 'in_review'])

    if (error) {
      console.error('Failed to fetch scoreboard report availability', {
        message: error.message,
        chunkStart: index,
        chunkSize: chunk.length,
      })
      return { reports: [], loaded: false }
    }

    reports.push(...((data || []) as unknown as ScoreboardVisibleReportRow[]))
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

  for (let index = 0; index < normalizedSlugs.length; index += REPORT_AVAILABILITY_QUERY_CHUNK_SIZE) {
    const chunk = normalizedSlugs.slice(index, index + REPORT_AVAILABILITY_QUERY_CHUNK_SIZE)
    const { data, error } = await supabase
      .from('project_reports')
      .select([
        'project_id',
        'id',
        'report_type',
        'version',
        'is_latest',
        'language',
        'published_at',
        'updated_at',
        'created_at',
        'gdrive_urls_by_lang',
        'file_urls_by_lang',
        'slide_html_urls_by_lang',
        'tracked_projects!inner(slug)',
      ].join(', '))
      .in('tracked_projects.slug', chunk)
      .in('report_type', ['econ', 'maturity', 'forensic'])
      .in('status', ['published', 'coming_soon', 'in_review'])

    if (error) {
      console.error('Failed to fetch scoreboard canonical alias report availability', {
        message: error.message,
        chunkStart: index,
        chunkSize: chunk.length,
      })
      return { reports: [], loaded: false }
    }

    reports.push(...((data || []) as unknown as ScoreboardVisibleReportRowWithProjectSlug[]))
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
      const canonicalAvailability = canonicalTargetSlug
        ? availabilityByProjectSlug?.get(canonicalTargetSlug)
        : undefined
      const reportAvailability = getReportAvailability(project, availabilityByProjectId, canonicalAvailability)

      return {
        rank: toCmcCanonicalRank(snapshot.cmc_rank) ?? index + 1,
        name: getSnapshotDisplayName(snapshot, project),
        symbol: getSnapshotDisplaySymbol(snapshot, project),
        slug: canonicalTargetSlug || project?.slug || snapshot.slug,
        change24h: snapshot.change_24h == null ? null : toNumber(snapshot.change_24h),
        marketCap: toNumber(snapshot.market_cap),
        score: project?.maturity_score == null ? null : toNumber(project.maturity_score),
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
  const canonicalRows = snapshotRows
    .filter((row) => toCmcCanonicalRank(row.cmc_rank) !== null)
    .sort((a, b) => (toCmcCanonicalRank(a.cmc_rank) ?? 0) - (toCmcCanonicalRank(b.cmc_rank) ?? 0))

  if (!hasCompleteCmcCanonicalTop200Snapshot(canonicalRows)) return []
  return snapshotRowsToScoreRows(
    canonicalRows,
    buildTrackedProjectLookup(trackedProjects, { includeProjectAliases: false }),
    availabilityByProjectId,
    availabilityByProjectSlug,
    buildTrackedProjectIdentityLookup(trackedProjects),
  )
}

export function hasCompleteCmcCanonicalTop200Snapshot(snapshotRows: ScoreboardSnapshotRow[]) {
  if (snapshotRows.length !== MIN_CMC_CANONICAL_TOP_200_SNAPSHOT_ROWS) return false

  const ranks = new Set(snapshotRows.map((row) => toCmcCanonicalRank(row.cmc_rank)))
  if (ranks.has(null) || ranks.size !== MIN_CMC_CANONICAL_TOP_200_SNAPSHOT_ROWS) return false

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
  const t = await getTranslations()
  const supabase = await createServerSupabaseClient()
  const projectsRepository = createProjectsRepository(supabase)

  const currentPage = Math.max(1, Math.min(2, parseInt(pageStr || '1', 10)))

  const [baseTrackedProjects, cmcSnapshotRows, canonicalAliasTargetProjects] = await Promise.all([
    projectsRepository.getProjectsForScoreboard(),
    projectsRepository.getLatestScoreboardMarketSnapshot(MAX_RANK),
    fetchScoreboardCanonicalAliasTargetProjects(),
  ])
  const trackedProjects = mergeScoreboardProjects(baseTrackedProjects, canonicalAliasTargetProjects)
  const trackedProjectIds = trackedProjects.map((project) => project.id).filter(Boolean)
  let visibleReportResult: Awaited<ReturnType<typeof fetchVisibleReportsForScoreboard>>
  let canonicalAliasReportResult: Awaited<ReturnType<typeof fetchVisibleReportsForScoreboardByProjectSlugs>>
  try {
    ;[visibleReportResult, canonicalAliasReportResult] = await Promise.all([
      fetchVisibleReportsForScoreboard(trackedProjectIds),
      fetchVisibleReportsForScoreboardByProjectSlugs(SCOREBOARD_CANONICAL_ALIAS_TARGET_SLUGS),
    ])
  } catch (error) {
    console.error('Failed to initialize scoreboard report availability boundary', {
      message: error instanceof Error ? error.message : String(error),
    })
    visibleReportResult = { reports: [], loaded: false }
    canonicalAliasReportResult = { reports: [], loaded: false }
  }
  const reportAvailabilityByProjectId = visibleReportResult.loaded
    ? buildReportAvailabilityByProjectId(visibleReportResult.reports, locale)
    : undefined
  const reportAvailabilityByProjectSlug = canonicalAliasReportResult.loaded
    ? buildReportAvailabilityByProjectSlug(canonicalAliasReportResult.reports, locale)
    : undefined

  const allRows = canonicalSnapshotRowsToScoreRows(
    cmcSnapshotRows,
    trackedProjects,
    reportAvailabilityByProjectId,
    reportAvailabilityByProjectSlug,
  )

  // Paginate: 100 per page
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE
  const endIdx = startIdx + ITEMS_PER_PAGE
  const rows = allRows.slice(startIdx, endIdx)
  const totalPages = Math.ceil(Math.min(allRows.length, MAX_RANK) / ITEMS_PER_PAGE)

  const isKo = locale === 'ko'

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-bold mb-3">
          {isKo ? '리포트' : 'Report'}
        </h1>
        <p className="text-gray-400 max-w-xl mx-auto">
          {isKo
            ? '시가총액 200위 종목들의 BCE 보고서를 확인하세요'
            : 'Crypto project rankings by market cap with BCE analysis reports'}
        </p>
      </div>

      {/* Page indicator */}
      {totalPages > 1 && (
        <div className="mb-4 text-center">
          <span className="text-sm text-gray-400">
            {isKo
              ? `${startIdx + 1}-${Math.min(endIdx, allRows.length)}위 (전체 ${allRows.length}개 프로젝트)`
              : `Rank ${startIdx + 1}-${Math.min(endIdx, allRows.length)} of ${allRows.length} projects`}
          </span>
        </div>
      )}

      {/* Market cap ranking table with email gate */}
      {rows.length > 0 ? (
        <ScoreTableGate
          rows={rows}
          freeLimit={200}
          locale={locale}
          currentPage={currentPage}
          totalPages={totalPages}
          className="max-h-[clamp(320px,calc(100dvh-18rem),640px)] overflow-auto overscroll-contain pr-1"
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

      {/* Newsletter CTA */}
      <div className="mt-16 p-8 rounded-2xl bg-gradient-to-r from-indigo-500/5 to-purple-500/5 border border-indigo-500/15 text-center">
        <h3 className="text-xl font-bold mb-2">
          {isKo ? '시장 업데이트 알림 받기' : 'Get Market Update Alerts'}
        </h3>
        <p className="text-gray-400 text-sm mb-4">
          {isKo
            ? '새로운 보고서와 시장 변동 알림을 받아보세요'
            : 'Be the first to know about new reports and market movements'}
        </p>
        <SubscribeForm
          locale={locale}
          source="newsletter"
          translations={{
            placeholder: t('subscribe.emailPlaceholder'),
            cta: t('subscribe.cta'),
            success: t('subscribe.checkEmail'),
          }}
        />
      </div>

      {/* Stats */}
      <div className="mt-10 pt-6 border-t border-white/5 flex justify-center gap-8 text-sm text-gray-600">
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{allRows.length}</div>
          <div>{isKo ? '상위 프로젝트' : 'Top Projects'}</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white">
            {allRows.filter((r) => r.reportTypes.length > 0).length}
          </div>
          <div>{isKo ? '분석 보고서' : 'Reports'}</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{totalPages}</div>
          <div>{isKo ? '페이지' : 'Pages'}</div>
        </div>
      </div>
    </div>
  )
}
