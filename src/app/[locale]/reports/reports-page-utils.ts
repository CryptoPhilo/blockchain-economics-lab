import type { ProjectReport } from '@/lib/types'
import { reportSupportsLocale } from '@/lib/report-locale'
import { compareReportVersions, sortReportsLatestFirst } from '@/lib/report-versioning'

function getRapidChangeTimestampSource(
  report: Pick<ProjectReport, 'source_modified_time' | 'published_at' | 'created_at' | 'updated_at'>,
): string | null | undefined {
  return report.source_modified_time || report.published_at || report.updated_at || report.created_at
}

function getEffectiveTimestamp(
  report: Pick<ProjectReport, 'source_modified_time' | 'published_at' | 'created_at' | 'updated_at'>,
): number {
  const source = getRapidChangeTimestampSource(report)

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

function isWithinRapidChangeWindow(report: ProjectReport, since: Date): boolean {
  const source = getRapidChangeTimestampSource(report)
  if (!source) return false

  const timestamp = new Date(source).getTime()
  return !Number.isNaN(timestamp) && timestamp >= since.getTime()
}

function reportBelongsToLocale(report: ProjectReport, locale: string): boolean {
  if (isRapidChangeCandidate(report)) return true
  return reportSupportsLocale(report, locale)
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
    source_modified_time: undefined,
    published_at: undefined,
    updated_at: undefined,
    created_at: a.created_at,
  }) - getEffectiveTimestamp({
    source_modified_time: undefined,
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

export function dedupeLatestReportsByProject(reports: ProjectReport[]): ProjectReport[] {
  const latestByProject = new Map<string, ProjectReport>()

  for (const report of reports) {
    const current = latestByProject.get(report.project_id)

    if (!current || compareRapidChangeReports(report, current) > 0) {
      latestByProject.set(report.project_id, report)
    }
  }

  return Array.from(latestByProject.values()).sort((a, b) => compareRapidChangeReports(b, a))
}

export function buildReportHistoryByProject(reports: ProjectReport[], latestReports: ProjectReport[]) {
  const latestByProject = new Map(latestReports.map((report) => [report.project_id, report]))
  const historyByProject = new Map<string, ProjectReport[]>()

  for (const report of sortReportsLatestFirst(reports)) {
    const latest = latestByProject.get(report.project_id)
    if (!latest) continue
    if (report.report_type !== latest.report_type) continue
    if (report.language !== latest.language) continue
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
  since?: Date
}) {
  const normalizedQuery = args.searchQuery?.trim().toLowerCase() || ''
  const filteredReports = normalizedQuery
    ? args.reports.filter((report) => getSearchableText(report).includes(normalizedQuery))
    : args.reports
  const windowReports = filteredReports.filter((report) => (
    !args.since || isWithinRapidChangeWindow(report, args.since)
  ))
  const latestReports = dedupeLatestReportsByProject(windowReports)
    .filter((report) => reportBelongsToLocale(report, args.locale))
    .filter((report) => isRapidChangeCandidate(report) || reportSupportsLocale(report, args.locale))
  const localeReports = windowReports.filter((report) => reportBelongsToLocale(report, args.locale))

  const historyByProject = buildReportHistoryByProject(localeReports, latestReports)
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
