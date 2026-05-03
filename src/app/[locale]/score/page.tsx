import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createProjectsRepository } from '@/lib/repositories/projects'
import ScoreTableGate from '@/components/ScoreTableGate'
import SubscribeForm from '@/components/SubscribeForm'

/**
 * CMC-Style Market Cap Ranking Page + Report Badges (BCE-379)
 *
 * Shows top 200 projects by market cap across 2 pages (100 per page).
 * Each row includes price, 24h change, market cap, BCE Score, and report badges.
 * Data: latest CMC market_data_daily snapshot, enriched by tracked_projects.
 */

const ITEMS_PER_PAGE = 100
const MAX_RANK = 200
export const MIN_CMC_CANONICAL_TOP_200_SNAPSHOT_ROWS = 200

type TrackedScoreboardProject = Awaited<
  ReturnType<ReturnType<typeof createProjectsRepository>['getProjectsForScoreboard']>
>[number]

type ScoreboardSnapshotRow = Awaited<
  ReturnType<ReturnType<typeof createProjectsRepository>['getLatestScoreboardMarketSnapshot']>
>[number]

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

function addProjectLookup(
  lookup: Map<string, TrackedScoreboardProject>,
  key: unknown,
  project: TrackedScoreboardProject
) {
  const normalized = normalizeKey(key)
  if (normalized && !lookup.has(normalized)) {
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
        addProjectLookup(lookup, alias, project)
      }
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

function buildReportTypes(project: TrackedScoreboardProject | undefined) {
  const reportTypes: string[] = []
  if (project?.last_econ_report_at) reportTypes.push('econ')
  if (project?.last_maturity_report_at) reportTypes.push('maturity')
  if (project?.last_forensic_report_at) reportTypes.push('forensic')
  return reportTypes
}

export function snapshotRowsToScoreRows(
  snapshotRows: ScoreboardSnapshotRow[],
  trackedLookup: Map<string, TrackedScoreboardProject>
) {
  return snapshotRows
    .slice(0, MAX_RANK)
    .map((snapshot, index) => {
      const project = trackedLookup.get(normalizeKey(snapshot.slug) || '')
      const reportTypes = buildReportTypes(project)

      return {
        rank: index + 1,
        name: project?.name || formatSnapshotName(snapshot.slug),
        symbol: project?.symbol || formatSnapshotSymbol(snapshot.slug),
        slug: project?.slug || snapshot.slug,
        change24h: snapshot.change_24h == null ? null : toNumber(snapshot.change_24h),
        marketCap: toNumber(snapshot.market_cap),
        score: project?.maturity_score == null ? null : toNumber(project.maturity_score),
        category: project?.category || '',
        reportTypes,
        reportDates: {
          econ: project?.last_econ_report_at ?? null,
          maturity: project?.last_maturity_report_at ?? null,
          forensic: project?.last_forensic_report_at ?? null,
        },
      }
    })
}

function fallbackProjectsToScoreRows(projects: TrackedScoreboardProject[]) {
  return projects
    .slice(0, MAX_RANK)
    .map((project, index) => {
      const reportTypes = buildReportTypes(project)

      return {
        rank: index + 1,
        name: project.name,
        symbol: project.symbol,
        slug: project.slug,
        change24h: null,
        marketCap: toNumber(project.market_cap_usd),
        score: project.maturity_score == null ? null : toNumber(project.maturity_score),
        category: project.category || '',
        reportTypes,
        reportDates: {
          econ: project.last_econ_report_at ?? null,
          maturity: project.last_maturity_report_at ?? null,
          forensic: project.last_forensic_report_at ?? null,
        },
      }
    })
}

export function hasCompleteCmcCanonicalTop200Snapshot(snapshotRowCount: number) {
  return snapshotRowCount >= MIN_CMC_CANONICAL_TOP_200_SNAPSHOT_ROWS
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

  const [trackedProjects, cmcSnapshotRows] = await Promise.all([
    projectsRepository.getProjectsForScoreboard(),
    projectsRepository.getLatestScoreboardMarketSnapshot(MAX_RANK),
  ])

  const trackedLookup = buildTrackedProjectLookup(trackedProjects)
  // Partial CMC snapshots are not canonical Top 200 data; use tracked projects instead.
  const usingTrackedProjectFallback = !hasCompleteCmcCanonicalTop200Snapshot(cmcSnapshotRows.length)
  const allRows = usingTrackedProjectFallback
    ? fallbackProjectsToScoreRows(trackedProjects)
    : snapshotRowsToScoreRows(cmcSnapshotRows, trackedLookup)

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
