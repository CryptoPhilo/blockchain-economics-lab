import { cleanCardSummary } from './report-summary'
import { pickLocaleReport } from './report-locale'
import type { Product, ProjectReport, ReportType, TrackedProject } from './types'

export type ReportWithCover = ProjectReport & {
  tracked_projects?: Pick<TrackedProject, 'id' | 'name' | 'slug' | 'symbol' | 'chain' | 'category'> | null
  product?: Pick<
    Product,
    | 'id'
    | 'slug'
    | 'title_en'
    | 'title_ko'
    | 'title_fr'
    | 'title_es'
    | 'title_de'
    | 'title_ja'
    | 'title_zh'
    | 'cover_image_url'
    | 'published_at'
  > | Pick<
    Product,
    | 'id'
    | 'slug'
    | 'title_en'
    | 'title_ko'
    | 'title_fr'
    | 'title_es'
    | 'title_de'
    | 'title_ja'
    | 'title_zh'
    | 'cover_image_url'
    | 'published_at'
  >[] | null
}

export const reportTypeLabels: Record<ReportType, { en: string; ko: string; tone: string }> = {
  econ: {
    en: 'ECON',
    ko: 'ECON',
    tone: 'border-sky-300/30 bg-sky-300/10 text-sky-100',
  },
  maturity: {
    en: 'MAT',
    ko: 'MAT',
    tone: 'border-emerald-300/30 bg-emerald-300/10 text-emerald-100',
  },
  forensic: {
    en: 'FOR',
    ko: 'FOR',
    tone: 'border-rose-300/30 bg-rose-300/10 text-rose-100',
  },
}

const REPORT_COVER_TYPES = new Set<ReportType>(['econ', 'maturity', 'forensic'])
const ENGLISH_PREVIEW_FALLBACK_LOCALES = new Set(['de', 'es', 'fr'])

function getReportPublishedTime(report: ReportWithCover) {
  const product = getProduct(report)
  const dateValue = report.published_at ?? product?.published_at ?? report.updated_at ?? report.created_at

  if (!dateValue) return 0

  const timestamp = Date.parse(dateValue)
  return Number.isNaN(timestamp) ? 0 : timestamp
}

function sortReportsByPublishedDate(reports: ReportWithCover[]) {
  return [...reports].sort((a, b) => {
    const publishedDelta = getReportPublishedTime(b) - getReportPublishedTime(a)
    if (publishedDelta !== 0) return publishedDelta

    return (b.version ?? 0) - (a.version ?? 0)
  })
}

export function getProduct(report: ReportWithCover) {
  return Array.isArray(report.product) ? report.product[0] : report.product
}

export function hasReportCover(report: ReportWithCover) {
  return Boolean(getProduct(report)?.cover_image_url?.trim())
}

function getSlidePreviewUrl(report: ReportWithCover, locale: string) {
  const slideUrls = report.slide_html_urls_by_lang as Record<string, unknown> | undefined
  const localized = slideUrls?.[locale]
  const languageMatched = report.language ? slideUrls?.[report.language] : undefined
  const englishFallback = ENGLISH_PREVIEW_FALLBACK_LOCALES.has(locale) ? slideUrls?.en : undefined
  const value = localized ?? englishFallback ?? languageMatched

  return typeof value === 'string' && value.trim() ? value : ''
}

function getSlideThumbnailUrl(report: ReportWithCover, locale: string) {
  const slidePreviewUrl = getSlidePreviewUrl(report, locale)
  if (!slidePreviewUrl) return ''

  try {
    const parsed = new URL(slidePreviewUrl)
    const marker = '/storage/v1/object/public/slides/'
    const index = parsed.pathname.indexOf(marker)
    if (index === -1) return ''

    const objectPath = parsed.pathname.slice(index + marker.length)
    const thumbnailPath = `showcase-thumbnails-v2/${objectPath.replace(/\.html$/i, '.jpg')}`
    return `${parsed.origin}${marker}${thumbnailPath}`
  } catch {
    return ''
  }
}

export function getShowcasePreview(report: ReportWithCover, locale: string): { url: string; kind: 'image' | 'html' } {
  const slideThumbnailUrl = getSlideThumbnailUrl(report, locale)
  if (slideThumbnailUrl) {
    return { url: slideThumbnailUrl, kind: 'image' }
  }

  const coverImageUrl = getProduct(report)?.cover_image_url?.trim()
  if (coverImageUrl) {
    return { url: coverImageUrl, kind: 'image' }
  }

  return { url: '', kind: 'html' }
}

function hasShowcasePreview(report: ReportWithCover, locale: string) {
  return Boolean(getShowcasePreview(report, locale).url)
}

export function dedupeLatestReportCoverCandidates(reports: ReportWithCover[]): ReportWithCover[] {
  const latestByProjectType = new Map<string, ReportWithCover>()

  for (const report of sortReportsByPublishedDate(reports)) {
    const key = `${report.project_id}:${report.report_type}`
    if (!latestByProjectType.has(key)) {
      latestByProjectType.set(key, report)
    }
  }

  return Array.from(latestByProjectType.values())
}

export function isPublishedReportCoverCandidate(report: ReportWithCover, locale?: string) {
  return REPORT_COVER_TYPES.has(report.report_type)
    && report.status === 'published'
    && (locale ? hasShowcasePreview(report, locale) : hasReportCover(report))
}

export function selectLatestReportShowcaseCandidates(
  reports: ReportWithCover[],
  locale: string,
  limit = 6,
): ReportWithCover[] {
  const reportsByProjectTypeVersion = new Map<string, ReportWithCover[]>()

  for (const report of reports) {
    if (!REPORT_COVER_TYPES.has(report.report_type) || report.status !== 'published') continue
    const key = `${report.project_id}:${report.report_type}:${report.version}`
    const siblings = reportsByProjectTypeVersion.get(key) ?? []
    siblings.push(report)
    reportsByProjectTypeVersion.set(key, siblings)
  }

  const selected: ReportWithCover[] = []
  const seenProjectTypes = new Set<string>()

  for (const report of sortReportsByPublishedDate(reports)) {
    if (!REPORT_COVER_TYPES.has(report.report_type) || report.status !== 'published') continue

    const projectTypeKey = `${report.project_id}:${report.report_type}`
    if (seenProjectTypes.has(projectTypeKey)) continue

    const siblingKey = `${report.project_id}:${report.report_type}:${report.version}`
    const siblings = reportsByProjectTypeVersion.get(siblingKey) ?? [report]
    const localizedReport = pickLocaleReport(siblings, locale) ?? siblings[0] ?? report

    seenProjectTypes.add(projectTypeKey)

    if (hasShowcasePreview(localizedReport, locale)) {
      selected.push(localizedReport)
    }

    if (selected.length >= limit) break
  }

  return selected
}

export function getReportHref(report: ReportWithCover, locale: string) {
  const project = report.tracked_projects ?? report.project
  if (!project?.slug) return `/${locale}/reports`

  if (report.report_type === 'forensic') {
    return `/${locale}/reports/forensic/${project.slug}`
  }

  return `/${locale}/reports/${project.slug}/${report.report_type}`
}

export function getLocalizedProductTitle(report: ReportWithCover, locale: string) {
  const product = getProduct(report)
  const localized = product?.[`title_${locale}` as keyof typeof product]

  if (typeof localized === 'string' && localized.trim()) return localized
  if (product?.title_en?.trim()) return product.title_en
  if (report.title_en?.trim()) return report.title_en

  return report.tracked_projects?.name ?? report.project?.name ?? 'BCELab Report'
}

export function getLocalizedSummary(report: ProjectReport, locale: string) {
  const cardData = report.card_data
  const localizedSummary = cardData?.summary_by_lang?.[locale]
    ?? report[`card_summary_${locale}` as keyof ProjectReport]
  const fallback = cardData?.summary_by_lang?.en
    ?? cardData?.summary_en
    ?? report.card_summary_en
    ?? cardData?.summary

  return cleanCardSummary(
    typeof localizedSummary === 'string' && localizedSummary.trim()
      ? localizedSummary
      : typeof fallback === 'string'
        ? fallback
        : '',
  )
}

export function formatReportDate(report: ReportWithCover, locale: string) {
  const dateValue = report.published_at ?? getProduct(report)?.published_at ?? report.updated_at ?? report.created_at
  if (!dateValue) return null

  return new Intl.DateTimeFormat(locale === 'ko' ? 'ko-KR' : 'en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(dateValue))
}
