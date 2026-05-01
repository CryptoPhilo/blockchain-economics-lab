import type { ProjectReport } from '@/lib/types'
import { reportSupportsLocale } from '@/lib/report-locale'

function getEffectiveTimestamp(report: Pick<ProjectReport, 'published_at' | 'created_at'>): number {
  const source = report.published_at || report.created_at

  if (!source) {
    return Number.NEGATIVE_INFINITY
  }

  const timestamp = new Date(source).getTime()
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp
}

function getStatusRank(report: Pick<ProjectReport, 'status'>): number {
  return report.status === 'published' ? 1 : 0
}

function compareRapidChangeReports(a: ProjectReport, b: ProjectReport): number {
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
    created_at: a.created_at,
  }) - getEffectiveTimestamp({
    published_at: undefined,
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

export function prepareRapidChangeReports(args: {
  reports: ProjectReport[]
  locale: string
  page: number
  pageSize: number
  searchQuery?: string
}) {
  const normalizedQuery = args.searchQuery?.trim().toLowerCase() || ''
  const localizedReports = args.reports.filter((report) => reportSupportsLocale(report, args.locale))
  const filteredReports = normalizedQuery
    ? localizedReports.filter((report) => getSearchableText(report).includes(normalizedQuery))
    : localizedReports

  const dedupedReports = dedupeLatestReportsByProject(filteredReports)
  const totalCount = dedupedReports.length
  const totalPages = totalCount > 0 ? Math.ceil(totalCount / args.pageSize) : 0
  const currentPage = totalCount > 0
    ? Math.min(Math.max(1, args.page), totalPages)
    : 1
  const from = (currentPage - 1) * args.pageSize
  const to = from + args.pageSize

  return {
    reports: dedupedReports.slice(from, to),
    totalCount,
    totalPages,
    currentPage,
  }
}
