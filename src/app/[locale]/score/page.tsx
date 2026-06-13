import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import { createProjectsRepository } from '@/lib/repositories/projects'
import { reportSupportsLocale } from '@/lib/report-locale'
import { pickLatestReport } from '@/lib/report-versioning'
import type { ProjectReport } from '@/lib/types'
import type { SupabaseClient } from '@supabase/supabase-js'
import ScoreTableGate from '@/components/ScoreTableGate'

export const dynamic = 'force-dynamic'
export const revalidate = 0

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
const REPORT_AVAILABILITY_QUERY_PAGE_SIZE = 1000
const SCORE_HEADER_BACKGROUND_IMAGE = '/images/score-header-bg.png'
export const MIN_CMC_CANONICAL_TOP_500_SNAPSHOT_ROWS = 500
const SCOREBOARD_CANONICAL_ALIASES = [
  { alias: 'ethena-usde', slug: 'ethena' },
  { alias: 'usde', slug: 'ethena' },
  { alias: 'global-dollar', slug: 'usdg' },
  { alias: 'agora-finance', slug: 'ausd' },
  { alias: 'sei-network', slug: 'sei' },
  { alias: 'pancakeswap-token', slug: 'pancakeswap' },
  { alias: 'injective-protocol', slug: 'injective' },
  { alias: 'curve-dao-token', slug: 'curve-dao' },
  { alias: 'blockstack', slug: 'stacks' },
  { alias: 'fetch-ai', slug: 'artificial-superintelligence-alliance' },
  { alias: 'euro-coin', slug: 'eurc' },
  { alias: 'eur-coinvertible', slug: 'eur-coinvertible' },
  { alias: 'euro-coinvertible', slug: 'eur-coinvertible' },
  { alias: 'eurcv', slug: 'eur-coinvertible' },
  { alias: 'siren-bsc', slug: 'siren' },
  { alias: 'river-protocol', slug: 'river' },
  { alias: 'flare', slug: 'flare-networks' },
  { alias: 'htx', slug: 'htx-dao' },
  { alias: 'htx-token', slug: 'htx-dao' },
  { alias: 'world-liberty-financial', slug: 'usd1' },
  { alias: 'polygon-ecosystem-token', slug: 'matic-network' },
  { alias: 'pol-ex-matic', slug: 'matic-network' },
  { alias: 'humanity', slug: 'humanity-protocol' },
  { alias: 'world-liberty-financial-wlfi', slug: 'world-liberty-financial' },
] as const

const SCOREBOARD_SYNTHETIC_PROJECTS = [
  {
    id: 'scoreboard-synthetic-eur-coinvertible',
    name: 'EUR CoinVertible',
    slug: 'eur-coinvertible',
    symbol: 'EURCV',
    category: 'Stablecoins',
    market_cap_usd: null,
    coingecko_id: null,
    cmc_id: 'eur-coinvertible',
    aliases: ['EUR CoinVertible', 'EURCV', 'eur-coinvertible', 'euro-coinvertible'],
    maturity_score: null,
    last_econ_report_at: null,
    last_maturity_report_at: null,
    last_forensic_report_at: null,
  },
] satisfies TrackedScoreboardProject[]

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

function isReportTypeKey(value: unknown): value is ReportTypeKey {
  return value === 'econ' || value === 'maturity' || value === 'forensic'
}

const SCOREBOARD_REPORT_AVAILABILITY_ALIASES = [
  { targetSlug: 'falcon-usd', sourceSlug: 'falcon-finance-ff' },
  { targetSlug: 'falcon-usd', sourceSlug: 'falcon-finance' },
] as const

function applyScoreboardReportAvailabilityAliases(
  availabilityByProjectId: Map<string, ReportAvailability>,
  projects: TrackedScoreboardProject[],
): void {
  const projectsBySlug = new Map(projects.map((project) => [project.slug, project]))

  for (const alias of SCOREBOARD_REPORT_AVAILABILITY_ALIASES) {
    const targetProject = projectsBySlug.get(alias.targetSlug)
    const sourceProject = projectsBySlug.get(alias.sourceSlug)

    if (!targetProject || !sourceProject) {
      continue
    }

    const sourceAvailability = availabilityByProjectId.get(sourceProject.id)

    if (!sourceAvailability) {
      continue
    }

    const targetAvailability = availabilityByProjectId.get(targetProject.id)

    availabilityByProjectId.set(targetProject.id, {
      reportTypes: Array.from(
        new Set([
          ...(targetAvailability?.reportTypes ?? []),
          ...sourceAvailability.reportTypes,
        ]),
      ),
      reportDates: {
        econ: targetAvailability?.reportDates.econ ?? sourceAvailability.reportDates.econ,
        maturity:
          targetAvailability?.reportDates.maturity ?? sourceAvailability.reportDates.maturity,
        forensic:
          targetAvailability?.reportDates.forensic ?? sourceAvailability.reportDates.forensic,
      },
    })
  }
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

function normalizeKey(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim().toLowerCase()
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

export function buildTrackedProjectLookup(projects: TrackedScoreboardProject[]) {
  const lookup = new Map<string, TrackedScoreboardProject>()

  for (const project of projects) {
    addProjectLookup(lookup, project.slug, project)
    addProjectLookup(lookup, project.coingecko_id, project)
    addProjectLookup(lookup, project.cmc_id, project)
    if (Array.isArray(project.aliases)) {
      for (const alias of project.aliases) {
        addProjectLookup(lookup, alias, project, { overwrite: true })
      }
    }
  }

  for (const project of SCOREBOARD_SYNTHETIC_PROJECTS) {
    addProjectLookup(lookup, project.slug, project)
    addProjectLookup(lookup, project.cmc_id, project)
    if (Array.isArray(project.aliases)) {
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
): ReportAvailability {
  const fallback = createFallbackReportAvailability(project)
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

export function buildReportAvailabilityByProjectId(
  reports: ScoreboardVisibleReportRow[],
  locale: string,
) {
  const map = new Map<string, ReportAvailability>()
  const reportsByProjectType = new Map<string, ScoreboardVisibleReportRow[]>()

  for (const report of reports) {
    if (!report.project_id) continue
    const key = `${report.project_id}:${report.report_type}`
    reportsByProjectType.set(key, [...(reportsByProjectType.get(key) ?? []), report])
  }

  for (const projectTypeReports of reportsByProjectType.values()) {
    const latest = pickLatestReport(projectTypeReports)
    if (!latest) continue

    const latestVersion = latest.version ?? null
    const localizedLatestVersionReports = projectTypeReports.filter((report) => (
      (report.version ?? null) === latestVersion
        && reportSupportsLocale(report as ProjectReport, locale)
    ))
    const report = pickLatestReport(localizedLatestVersionReports)
    if (!report) continue
    if (!isReportTypeKey(report.report_type)) continue
    const reportType = report.report_type

    const existing = map.get(report.project_id) ?? {
      reportTypes: [],
      reportDates: { econ: null, maturity: null, forensic: null },
    }

    if (!existing.reportTypes.includes(reportType)) {
      existing.reportTypes.push(reportType)
    }

    const timestamp = getReportTimestamp(report)
    const current = existing.reportDates[reportType]
    if (timestamp && (!current || new Date(timestamp).getTime() > new Date(current).getTime())) {
      existing.reportDates[reportType] = timestamp
    }

    map.set(report.project_id, existing)
  }

  return map
}

export async function fetchVisibleReportsForScoreboard(
  projectIds: string[],
  reportSupabase?: SupabaseClient,
  fallbackSupabase?: SupabaseClient,
): Promise<{ reports: ScoreboardVisibleReportRow[]; loaded: boolean }> {
  if (projectIds.length === 0) {
    return { reports: [], loaded: true }
  }

  const clients = [reportSupabase, fallbackSupabase].filter(Boolean) as SupabaseClient[]
  if (clients.length === 0) return { reports: [], loaded: false }

  const loadFromClient = async (client: SupabaseClient) => {
    const reports: ScoreboardVisibleReportRow[] = []

    for (let index = 0; index < projectIds.length; index += REPORT_AVAILABILITY_QUERY_CHUNK_SIZE) {
      const chunk = projectIds.slice(index, index + REPORT_AVAILABILITY_QUERY_CHUNK_SIZE)

      for (let offset = 0; ; offset += REPORT_AVAILABILITY_QUERY_PAGE_SIZE) {
        const { data, error } = await client
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
          .range(offset, offset + REPORT_AVAILABILITY_QUERY_PAGE_SIZE - 1)

        if (error) {
          return { reports: [], error: error.message }
        }

        const batch = (data || []) as unknown as ScoreboardVisibleReportRow[]
        reports.push(...batch)
        if (batch.length < REPORT_AVAILABILITY_QUERY_PAGE_SIZE) break
      }
    }

    return { reports, error: null as string | null }
  }

  for (const client of clients) {
    const result = await loadFromClient(client)

    if (!result.error) {
      return { reports: result.reports, loaded: true }
    }

    console.error('Failed to fetch scoreboard report availability', {
      message: result.error,
    })
  }

  return { reports: [], loaded: false }
}

export function snapshotRowsToScoreRows(
  snapshotRows: ScoreboardSnapshotRow[],
  trackedLookup: Map<string, TrackedScoreboardProject>,
  availabilityByProjectId?: Map<string, ReportAvailability>,
) {
  return snapshotRows
    .slice(0, MAX_RANK)
    .map((snapshot, index) => {
      const project = trackedLookup.get(normalizeKey(snapshot.slug) || '')
      const reportAvailability = getReportAvailability(project, availabilityByProjectId)

      return {
        rank: toCmcCanonicalRank(snapshot.cmc_rank) ?? index + 1,
        name: project?.name || formatSnapshotName(snapshot.slug),
        symbol: project?.symbol || formatSnapshotSymbol(snapshot.slug),
        slug: project?.slug || snapshot.slug,
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
) {
  const canonicalRows = snapshotRows
    .filter((row) => toCmcCanonicalRank(row.cmc_rank) !== null)
    .sort((a, b) => (toCmcCanonicalRank(a.cmc_rank) ?? 0) - (toCmcCanonicalRank(b.cmc_rank) ?? 0))

  if (!hasCompleteCmcCanonicalTop500Snapshot(canonicalRows)) return []
  return snapshotRowsToScoreRows(
    canonicalRows,
    buildTrackedProjectLookup(trackedProjects),
    availabilityByProjectId,
  )
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
  const supabase = await createServerSupabaseClient()
  const projectsRepository = createProjectsRepository(supabase)

  const currentPage = Math.max(1, Math.min(5, parseInt(pageStr || '1', 10)))

  const [trackedProjects, cmcSnapshotRows] = await Promise.all([
    projectsRepository.getProjectsForScoreboard(),
    projectsRepository.getLatestScoreboardMarketSnapshot(MAX_RANK),
  ])
  const trackedProjectIds = trackedProjects.map((project) => project.id).filter(Boolean)
  let reportClient: SupabaseClient | undefined
  try {
    reportClient = createSupabaseAdminClient()
  } catch (error) {
    console.error('Using anonymous Supabase client for report availability (admin key unavailable)', {
      message: error instanceof Error ? error.message : String(error),
    })
  }
  let visibleReportResult: Awaited<ReturnType<typeof fetchVisibleReportsForScoreboard>>
  try {
    visibleReportResult = await fetchVisibleReportsForScoreboard(trackedProjectIds, reportClient, supabase)
  } catch (error) {
    console.error('Failed to initialize scoreboard report availability boundary', {
      message: error instanceof Error ? error.message : String(error),
    })
    visibleReportResult = { reports: [], loaded: false }
  }
  const reportAvailabilityByProjectId = visibleReportResult.loaded
    ? buildReportAvailabilityByProjectId(visibleReportResult.reports, locale)
    : undefined

  if (reportAvailabilityByProjectId) {
    applyScoreboardReportAvailabilityAliases(reportAvailabilityByProjectId, trackedProjects)
  }

  const allRows = canonicalSnapshotRowsToScoreRows(
    cmcSnapshotRows,
    trackedProjects,
    reportAvailabilityByProjectId,
  )

  // Paginate: 100 per page
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE
  const endIdx = startIdx + ITEMS_PER_PAGE
  const rows = allRows.slice(startIdx, endIdx)
  const totalPages = Math.ceil(Math.min(allRows.length, MAX_RANK) / ITEMS_PER_PAGE)

  const isKo = locale === 'ko'

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
      {/* Header */}
      <section
        className="relative mb-6 overflow-hidden rounded-2xl border border-white/10 bg-slate-950 bg-cover bg-center px-6 py-16 text-center shadow-2xl shadow-black/30 sm:px-10 sm:py-20"
        style={{
          backgroundImage: `linear-gradient(180deg, rgba(3, 7, 18, 0.46), rgba(3, 7, 18, 0.78)), url(${SCORE_HEADER_BACKGROUND_IMAGE})`,
        }}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.08),transparent_38%)]" />
        <div className="relative mx-auto max-w-2xl">
          <h1 className="mb-4 text-4xl font-bold text-white drop-shadow-[0_2px_18px_rgba(0,0,0,0.85)] sm:text-5xl">
            {isKo ? '리포트' : 'Report'}
          </h1>
          <p className="mx-auto max-w-xl text-base font-medium leading-7 text-slate-200 drop-shadow-[0_2px_14px_rgba(0,0,0,0.8)] sm:text-lg">
            {isKo
              ? '시가총액 500위 종목들의 BCE 보고서를 확인하세요'
              : 'Crypto project rankings by market cap with BCE analysis reports'}
          </p>
        </div>
      </section>

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
          rowsPerPage={ITEMS_PER_PAGE}
          className="max-h-[clamp(460px,calc(100dvh-12rem),860px)] overflow-auto overscroll-y-auto pr-1"
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
