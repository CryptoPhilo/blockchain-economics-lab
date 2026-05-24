import LatestReportShowcaseCarousel, { type LatestReportShowcaseItem } from './LatestReportShowcaseCarousel'
import {
  formatReportDate,
  getLocalizedProductTitle,
  getLocalizedSummary,
  getProduct,
  getReportHref,
  isPublishedReportCoverCandidate,
  type ReportWithCover,
} from '@/lib/latest-report-showcase'

interface LatestReportShowcaseProps {
  reports: ReportWithCover[]
  locale: string
}

export default function LatestReportShowcase({ reports, locale }: LatestReportShowcaseProps) {
  const items: LatestReportShowcaseItem[] = reports
    .filter((report) => isPublishedReportCoverCandidate(report, locale))
    .slice(0, 6)
    .map((report) => {
      const product = getProduct(report)
      const project = report.tracked_projects ?? report.project

      return {
        id: report.id,
        href: getReportHref(report, locale),
        reportType: report.report_type,
        title: getLocalizedProductTitle(report, locale),
        summary: getLocalizedSummary(report, locale),
        projectName: project?.name,
        projectSymbol: project?.symbol,
        coverImageUrl: product?.cover_image_url ?? '',
        publishedDate: formatReportDate(report, locale),
      }
    })

  if (items.length === 0) return null

  return (
    <section className="bg-neutral-950 py-10 md:py-12">
      <LatestReportShowcaseCarousel items={items} locale={locale} />
    </section>
  )
}
