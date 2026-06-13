import LatestReportShowcaseCarousel, { type LatestReportShowcaseItem } from './LatestReportShowcaseCarousel'
import {
  formatReportDate,
  getLocalizedSummary,
  getReportHref,
  getShowcasePreview,
  getShowcaseDisplayTitle,
  isPublishedReportCoverCandidate,
  type ReportWithCover,
} from '@/lib/latest-report-showcase'

interface LatestReportShowcaseProps {
  reports: ReportWithCover[]
  locale: string
}

const supportedLocales = ['en', 'ko', 'fr', 'es', 'de', 'ja', 'zh'] as const

function hasLocalizedValue(value: unknown) {
  if (typeof value === 'string') return value.trim().length > 0
  return Boolean(value && typeof value === 'object')
}

function countLocalizedAssets(report: ReportWithCover) {
  const assetLocales = new Set<string>()
  const assetMaps = [
    report.gdrive_urls_by_lang,
    report.file_urls_by_lang,
    report.slide_html_urls_by_lang,
  ]

  for (const assetMap of assetMaps) {
    if (!assetMap || typeof assetMap !== 'object') continue
    for (const locale of supportedLocales) {
      if (hasLocalizedValue((assetMap as Record<string, unknown>)[locale])) {
        assetLocales.add(locale)
      }
    }
  }

  const translationStatus = report.translation_status
  if (translationStatus && typeof translationStatus === 'object') {
    for (const locale of supportedLocales) {
      if (translationStatus[locale] === 'completed') {
        assetLocales.add(locale)
      }
    }
  }

  return assetLocales.size
}

function hasPdfAsset(report: ReportWithCover) {
  return Boolean(
    report.file_url
    || report.gdrive_url
    || report.gdrive_download_url
    || Object.values(report.gdrive_urls_by_lang ?? {}).some(hasLocalizedValue)
    || Object.values(report.file_urls_by_lang ?? {}).some(hasLocalizedValue),
  )
}

function hasSlideAsset(report: ReportWithCover) {
  return Object.values(report.slide_html_urls_by_lang ?? {}).some(hasLocalizedValue)
}

export default function LatestReportShowcase({ reports, locale }: LatestReportShowcaseProps) {
  const items: LatestReportShowcaseItem[] = reports
    .filter((report) => isPublishedReportCoverCandidate(report, locale))
    .slice(0, 6)
    .map((report) => {
      const project = report.tracked_projects ?? report.project
      const preview = getShowcasePreview(report, locale)

      return {
        id: report.id,
        href: getReportHref(report, locale),
        reportType: report.report_type,
        title: getShowcaseDisplayTitle(report),
        summary: getLocalizedSummary(report, locale),
        projectName: project?.name,
        projectSymbol: project?.symbol,
        coverImageUrl: preview.url,
        previewKind: preview.kind,
        publishedDate: formatReportDate(report, locale),
        localeCount: countLocalizedAssets(report),
        hasPdfAsset: hasPdfAsset(report),
        hasSlideAsset: hasSlideAsset(report),
      }
    })

  if (items.length === 0) return null

  return (
    <section className="bg-slate-950 py-8 md:py-10">
      <LatestReportShowcaseCarousel items={items} locale={locale} />
    </section>
  )
}
