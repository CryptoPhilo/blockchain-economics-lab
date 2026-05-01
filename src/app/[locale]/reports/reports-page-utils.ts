import type { ProjectReport } from '@/lib/types'

type TranslationState = 'completed' | 'published'

const COMPLETED_TRANSLATION_STATES = new Set<TranslationState>(['completed', 'published'])

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

function hasNonEmptyValue(value: unknown): boolean {
  if (typeof value === 'string') {
    return value.trim().length > 0
  }

  if (Array.isArray(value)) {
    return value.some(hasNonEmptyValue)
  }

  return false
}

function hasLocalizedField(report: ProjectReport, locale: string, fieldPrefix: string): boolean {
  return hasNonEmptyValue((report as unknown as Partial<Record<string, unknown>>)[`${fieldPrefix}_${locale}`])
}

function hasLocalizedUrl(report: ProjectReport, locale: string): boolean {
  const gdriveUrls = report.gdrive_urls_by_lang as Record<string, unknown> | undefined
  const fileUrls = report.file_urls_by_lang as Record<string, unknown> | undefined

  return hasUrlEntry(gdriveUrls?.[locale]) || hasUrlEntry(fileUrls?.[locale])
}

function hasLocalizedCardData(report: ProjectReport, locale: string): boolean {
  return hasNonEmptyValue(report.card_data?.summary_by_lang?.[locale])
    || hasNonEmptyValue(report.card_data?.keywords_by_lang?.[locale])
}

function hasUrlEntry(value: unknown): boolean {
  if (typeof value === 'string') {
    return value.trim().length > 0
  }

  if (!value || typeof value !== 'object') {
    return false
  }

  const entry = value as { url?: unknown; download_url?: unknown }
  return hasNonEmptyValue(entry.url) || hasNonEmptyValue(entry.download_url)
}

function hasCompletedTranslation(report: ProjectReport, locale: string): boolean {
  const translationStatus = report.translation_status as Record<string, unknown> | undefined
  const status = translationStatus?.[locale]

  return typeof status === 'string' && COMPLETED_TRANSLATION_STATES.has(status as TranslationState)
}

export function reportSupportsLocale(report: ProjectReport, locale: string): boolean {
  if (!locale) {
    return true
  }

  if (report.language === locale) {
    return true
  }

  return hasLocalizedField(report, locale, 'title')
    || hasLocalizedField(report, locale, 'card_summary')
    || hasLocalizedUrl(report, locale)
    || hasLocalizedCardData(report, locale)
    || hasCompletedTranslation(report, locale)
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
