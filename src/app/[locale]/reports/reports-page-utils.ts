import type { ProjectReport } from '@/lib/types'
import { reportSupportsLocale } from '@/lib/report-locale'
import { compareReportVersions, sortReportsLatestFirst } from '@/lib/report-versioning'

function getEffectiveTimestamp(report: Pick<ProjectReport, 'published_at' | 'created_at' | 'updated_at'>): number {
  const source = report.published_at || report.updated_at || report.created_at

  if (!source) {
    return Number.NEGATIVE_INFINITY
  }

  const timestamp = new Date(source).getTime()
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp
}

function getStatusRank(report: Pick<ProjectReport, 'status'>): number {
  if (report.status === 'published') return 2
  if (report.status === 'in_review') return 1
  return 0
}

function isRapidChangeCandidate(report: ProjectReport): boolean {
  return (report.status === 'coming_soon' || report.status === 'in_review') && report.report_type === 'forensic'
}

function compareRapidChangeReports(a: ProjectReport, b: ProjectReport): number {
  const versionDelta = compareReportVersions(a, b)
  if (versionDelta !== 0) {
    return versionDelta
  }

  const effectiveTimeDelta = getEffectiveTimestamp(a) - getEffectiveTimestamp(b)
  if (effectiveTimeDelta !== 0) {
    return effectiveTimeDelta
  }

  const statusDelta = getStatusRank(a) - getStatusRank(b)
  if (statusDelta !== 0) {
    return statusDelta
  }

  const createdAtDelta = getEffectiveTimestamp({
    published_at: undefined,
    updated_at: undefined,
    created_at: a.created_at,
  }) - getEffectiveTimestamp({
    published_at: undefined,
    updated_at: undefined,
    created_at: b.created_at,
  })
  if (createdAtDelta !== 0) {
    return createdAtDelta
  }

  return a.id.localeCompare(b.id)
}

function getSearchableText(report: ProjectReport): string {
  const project = report.project
  const fields = [
    report.title_en,
    report.title_ko,
    report.title_fr,
    report.title_es,
    report.title_de,
    report.title_ja,
    report.title_zh,
    project?.name,
    project?.symbol,
    project?.slug,
  ]

  return fields.filter((value): value is string => typeof value === 'string' && value.length > 0)
    .join(' ')
    .toLowerCase()
}

function getRapidChangeAssetKey(report: ProjectReport): string {
  const project = report.project
  const symbol = project?.symbol?.trim().toUpperCase()
  if (symbol) return `symbol:${symbol}`

  const coingeckoId = project?.coingecko_id?.trim().toLowerCase()
  if (coingeckoId) return `coingecko:${coingeckoId}`

  return `project:${report.project_id}`
}

export function dedupeLatestReportsByProject(reports: ProjectReport[]): ProjectReport[] {
  const latestByAsset = new Map<string, ProjectReport>()

  for (const report of reports) {
    const assetKey = getRapidChangeAssetKey(report)
    const current = latestByAsset.get(assetKey)

    if (!current || compareRapidChangeReports(report, current) > 0) {
      latestByAsset.set(assetKey, report)
    }
  }

  return Array.from(latestByAsset.values()).sort((a, b) => compareRapidChangeReports(b, a))
}

export function buildReportHistoryByProject(reports: ProjectReport[], latestReports: ProjectReport[]) {
  const latestByProject = new Map(latestReports.map((report) => [report.project_id, report]))
  const historyByProject = new Map<string, ProjectReport[]>()

  for (const report of sortReportsLatestFirst(reports)) {
    const latest = latestByProject.get(report.project_id)
    if (!latest) continue
    if (report.report_type !== latest.report_type) continue
    if (Number(report.version || 0) >= Number(latest.version || 0)) continue

    const list = historyByProject.get(report.project_id) || []
    list.push(report)
    historyByProject.set(report.project_id, list)
  }

  return historyByProject
}

export function prepareRapidChangeReports(args: {
  reports: ProjectReport[]
  locale: string
  page: number
  pageSize: number
  searchQuery?: string
}) {
  const normalizedQuery = args.searchQuery?.trim().toLowerCase() || ''
  const filteredReports = normalizedQuery
    ? args.reports.filter((report) => getSearchableText(report).includes(normalizedQuery))
    : args.reports

  const latestReports = dedupeLatestReportsByProject(filteredReports)
    .filter((report) => isRapidChangeCandidate(report) || reportSupportsLocale(report, args.locale))
  const localizedHistoryReports = filteredReports.filter((report) => (
    isRapidChangeCandidate(report) || reportSupportsLocale(report, args.locale)
  ))
  const historyByProject = buildReportHistoryByProject(localizedHistoryReports, latestReports)
  const totalCount = latestReports.length
  const totalPages = totalCount > 0 ? Math.ceil(totalCount / args.pageSize) : 0
  const currentPage = totalCount > 0
    ? Math.min(Math.max(1, args.page), totalPages)
    : 1
  const from = (currentPage - 1) * args.pageSize
  const to = from + args.pageSize
  const pageReports = latestReports.slice(from, to)

  return {
    reports: pageReports,
    historyByProject,
    totalCount,
    totalPages,
    currentPage,
  }
}
