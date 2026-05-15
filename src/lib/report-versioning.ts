import type { ReportType } from './types'

export type ReportVersionRecord = {
  id?: string
  project_id: string
  report_type: ReportType | string
  version?: number | null
  language?: string | null
  published_at?: string | null
  updated_at?: string | null
  created_at?: string | null
  is_latest?: boolean | null
}

export type ReportVersionHistoryItem = ReportVersionRecord & {
  href: string
}

function getReportTimestamp(report: Pick<ReportVersionRecord, 'published_at' | 'updated_at' | 'created_at'>): number {
  const source = report.published_at || report.updated_at || report.created_at
  if (!source) return Number.NEGATIVE_INFINITY

  const timestamp = new Date(source).getTime()
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp
}

export function compareReportVersions(a: ReportVersionRecord, b: ReportVersionRecord): number {
  const latestDelta = Number(Boolean(a.is_latest)) - Number(Boolean(b.is_latest))
  if (latestDelta !== 0) return latestDelta

  const versionDelta = (a.version || 0) - (b.version || 0)
  if (versionDelta !== 0) return versionDelta

  const timestampDelta = getReportTimestamp(a) - getReportTimestamp(b)
  if (timestampDelta !== 0) return timestampDelta

  return (a.id || '').localeCompare(b.id || '')
}

export function sortReportsLatestFirst<T extends ReportVersionRecord>(reports: T[]): T[] {
  return [...reports].sort((a, b) => compareReportVersions(b, a))
}

export function pickLatestReport<T extends ReportVersionRecord>(reports: T[]): T | undefined {
  return sortReportsLatestFirst(reports)[0]
}

export function getReportVersionParam(value: string | string[] | undefined): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  if (!raw) return null

  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

export function pickRequestedOrLatestReport<T extends ReportVersionRecord>(
  reports: T[],
  args: { version?: number | null; language?: string | null },
): T | undefined {
  const requested = args.version
    ? reports.find((report) => (
        Number(report.version || 0) === args.version && (!args.language || report.language === args.language)
      ))
    : undefined

  if (requested) return requested
  return pickLatestReport(reports)
}

export function buildReportVersionHref(args: {
  baseHref: string
  version: number
  language?: string | null
  reportType?: ReportType | string | null
}) {
  const params = new URLSearchParams()
  params.set('version', String(args.version))
  if (args.language) params.set('lang', args.language)
  if (args.reportType) params.set('type', args.reportType)
  return `${args.baseHref}?${params.toString()}`
}

export function getReportVersionLabel(report: ReportVersionRecord) {
  const date = report.published_at || report.updated_at || report.created_at
  return {
    date,
    language: report.language || 'unknown',
    reportType: report.report_type,
    version: Number(report.version || 1),
  }
}
