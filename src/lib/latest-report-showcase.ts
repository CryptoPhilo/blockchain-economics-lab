import { cleanCardSummary } from './report-summary'
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

export function getProduct(report: ReportWithCover) {
  return Array.isArray(report.product) ? report.product[0] : report.product
}

export function hasReportCover(report: ReportWithCover) {
  return Boolean(getProduct(report)?.cover_image_url?.trim())
}

export function isPublishedReportCoverCandidate(report: ReportWithCover, _locale?: string) {
  return REPORT_COVER_TYPES.has(report.report_type)
    && report.status === 'published'
    && hasReportCover(report)
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
