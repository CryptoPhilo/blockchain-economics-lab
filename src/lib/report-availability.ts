import type { SupabaseClient } from '@supabase/supabase-js'
import { reportSupportsLocale } from '@/lib/report-locale'
import { pickLatestReport } from '@/lib/report-versioning'
import type { ProjectReport } from '@/lib/types'

const REPORT_AVAILABILITY_QUERY_CHUNK_SIZE = 80
const REPORT_AVAILABILITY_QUERY_PAGE_SIZE = 1000

export type ReportTypeKey = 'econ' | 'maturity' | 'forensic'

export type ReportAvailability = {
  reportTypes: string[]
  reportDates: Record<ReportTypeKey, string | null>
}

export type VisibleReportRow = {
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

export type ProjectReportAvailabilityCandidate = {
  id: string
  name: string
  slug: string
  symbol: string
  coingecko_id: string | null
  cmc_id: string | number | null
  aliases: string[] | null
}

function isReportTypeKey(value: unknown): value is ReportTypeKey {
  return value === 'econ' || value === 'maturity' || value === 'forensic'
}

function getReportTimestamp(report: {
  published_at?: string | null
  updated_at?: string | null
  created_at?: string | null
}) {
  return report.published_at || report.updated_at || report.created_at || null
}

function normalizeAvailabilityKey(value: unknown): string {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : ''
  }

  return typeof value === 'string' ? value.trim().toLowerCase() : ''
}

function normalizeNullableAvailabilityKey(value: unknown): string | null {
  const normalized = normalizeAvailabilityKey(value)
  return normalized || null
}

export function getProjectReportAvailabilityKeys(project: ProjectReportAvailabilityCandidate): string[] {
  const keys = [
    normalizeNullableAvailabilityKey(project.slug),
    normalizeNullableAvailabilityKey(project.coingecko_id),
    normalizeNullableAvailabilityKey(project.cmc_id),
    normalizeNullableAvailabilityKey(project.name),
    normalizeNullableAvailabilityKey(`${project.name}:${project.symbol}`),
  ]

  if (Array.isArray(project.aliases)) {
    for (const alias of project.aliases) {
      keys.push(normalizeNullableAvailabilityKey(alias))
    }
  }

  return Array.from(new Set(keys.filter((key): key is string => !!key)))
}

export function getMatchingProjectReportAliasIds(
  project: ProjectReportAvailabilityCandidate,
  candidateProjects: ProjectReportAvailabilityCandidate[],
): string[] {
  const projectKeys = new Set(getProjectReportAvailabilityKeys(project))

  return candidateProjects
    .filter((candidate) => (
      candidate.id === project.id
      || getProjectReportAvailabilityKeys(candidate).some((key) => projectKeys.has(key))
    ))
    .map((candidate) => candidate.id)
}

export function createEmptyReportAvailability(): ReportAvailability {
  return {
    reportTypes: [],
    reportDates: { econ: null, maturity: null, forensic: null },
  }
}

export function buildReportAvailabilityByProjectId(
  reports: VisibleReportRow[],
  locale: string,
) {
  const map = new Map<string, ReportAvailability>()
  const reportsByProjectType = new Map<string, VisibleReportRow[]>()

  for (const report of reports) {
    if (!report.project_id) continue
    const key = `${report.project_id}:${report.report_type}`
    reportsByProjectType.set(key, [...(reportsByProjectType.get(key) ?? []), report])
  }

  for (const projectTypeReports of reportsByProjectType.values()) {
    const localizedReports = projectTypeReports.filter((report) => (
      reportSupportsLocale(report as ProjectReport, locale)
    ))
    const report = pickLatestReport(localizedReports)
    if (!report) continue
    if (!isReportTypeKey(report.report_type)) continue
    const reportType = report.report_type

    const existing = map.get(report.project_id) ?? createEmptyReportAvailability()

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

function hasReportAvailability(availability: ReportAvailability | undefined): availability is ReportAvailability {
  return !!availability && availability.reportTypes.length > 0
}

export function applyProjectReportAvailabilityAliases(
  availabilityByProjectId: Map<string, ReportAvailability>,
  listedProjects: ProjectReportAvailabilityCandidate[],
  candidateProjects: ProjectReportAvailabilityCandidate[],
) {
  const availabilityByKey = new Map<string, ReportAvailability>()

  for (const project of candidateProjects) {
    const availability = availabilityByProjectId.get(project.id)
    if (!hasReportAvailability(availability)) continue

    for (const key of getProjectReportAvailabilityKeys(project)) {
      if (!availabilityByKey.has(key)) {
        availabilityByKey.set(key, availability)
      }
    }
  }

  for (const project of listedProjects) {
    if (hasReportAvailability(availabilityByProjectId.get(project.id))) continue

    for (const key of getProjectReportAvailabilityKeys(project)) {
      const availability = availabilityByKey.get(key)
      if (availability) {
        availabilityByProjectId.set(project.id, availability)
        break
      }
    }
  }
}

export async function fetchVisibleReportsForProjectIds(
  projectIds: string[],
  reportSupabase?: SupabaseClient,
  fallbackSupabase?: SupabaseClient,
): Promise<{ reports: VisibleReportRow[]; loaded: boolean }> {
  if (projectIds.length === 0) {
    return { reports: [], loaded: true }
  }

  const clients = [reportSupabase, fallbackSupabase].filter(Boolean) as SupabaseClient[]
  if (clients.length === 0) return { reports: [], loaded: false }

  const loadFromClient = async (client: SupabaseClient) => {
    const reports: VisibleReportRow[] = []

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

        const batch = (data || []) as unknown as VisibleReportRow[]
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

    console.error('Failed to fetch report availability', {
      message: result.error,
    })
  }

  return { reports: [], loaded: false }
}
