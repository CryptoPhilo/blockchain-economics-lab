import Image from 'next/image'
import Link from 'next/link'

import { cleanCardSummary } from '@/lib/report-summary'
import type { Product, ProjectReport, ReportType, TrackedProject } from '@/lib/types'

type ReportWithCover = ProjectReport & {
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

interface LatestReportShowcaseProps {
  reports: ReportWithCover[]
  locale: string
}

const reportTypeLabels: Record<ReportType, { en: string; ko: string; tone: string }> = {
  econ: {
    en: 'ECON',
    ko: '경제',
    tone: 'border-blue-400/30 bg-blue-400/10 text-blue-200',
  },
  maturity: {
    en: 'MATURITY',
    ko: '성숙도',
    tone: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
  },
  forensic: {
    en: 'FORENSIC',
    ko: '포렌식',
    tone: 'border-red-400/30 bg-red-400/10 text-red-200',
  },
}

function getProduct(report: ReportWithCover) {
  return Array.isArray(report.product) ? report.product[0] : report.product
}

export function hasReportCover(report: ReportWithCover) {
  return Boolean(getProduct(report)?.cover_image_url?.trim())
}

export function getReportHref(report: ReportWithCover, locale: string) {
  const project = report.tracked_projects ?? report.project
  if (!project?.slug) return `/${locale}/reports`

  if (report.report_type === 'forensic') {
    return `/${locale}/reports/forensic/${project.slug}`
  }

  return `/${locale}/reports/${project.slug}/${report.report_type}`
}

function getLocalizedProductTitle(report: ReportWithCover, locale: string) {
  const product = getProduct(report)
  const localized = product?.[`title_${locale}` as keyof typeof product]

  if (typeof localized === 'string' && localized.trim()) return localized
  if (product?.title_en?.trim()) return product.title_en
  if (report.title_en?.trim()) return report.title_en

  return report.tracked_projects?.name ?? report.project?.name ?? 'BCELab Report'
}

function getLocalizedSummary(report: ProjectReport, locale: string) {
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

function formatReportDate(report: ReportWithCover, locale: string) {
  const dateValue = report.published_at ?? getProduct(report)?.published_at ?? report.updated_at ?? report.created_at
  if (!dateValue) return null

  return new Intl.DateTimeFormat(locale === 'ko' ? 'ko-KR' : 'en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(dateValue))
}

export default function LatestReportShowcase({ reports, locale }: LatestReportShowcaseProps) {
  const coverReports = reports.filter(hasReportCover).slice(0, 4)
  const featured = coverReports[0]

  if (!featured) return null

  const isKo = locale === 'ko'
  const featuredProduct = getProduct(featured)
  const featuredProject = featured.tracked_projects ?? featured.project
  const featuredLabel = reportTypeLabels[featured.report_type] ?? reportTypeLabels.forensic
  const featuredSummary = getLocalizedSummary(featured, locale)
  const secondaryReports = coverReports.slice(1)

  return (
    <section className="bg-gray-950 py-14 md:py-18">
      <div className="mx-auto grid max-w-6xl gap-8 px-6 lg:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.72fr)] lg:items-center">
        <Link
          href={getReportHref(featured, locale)}
          className="group grid gap-6 rounded-xl border border-white/10 bg-white/[0.03] p-4 transition-colors hover:border-white/20 md:grid-cols-[minmax(260px,0.72fr)_minmax(0,1fr)] md:p-5"
        >
          <div className="relative aspect-[4/5] overflow-hidden rounded-lg bg-gray-900">
            <Image
              src={featuredProduct?.cover_image_url ?? ''}
              alt={getLocalizedProductTitle(featured, locale)}
              fill
              sizes="(min-width: 1024px) 430px, (min-width: 768px) 42vw, 92vw"
              className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
              priority
            />
          </div>
          <div className="flex min-w-0 flex-col justify-center px-1 py-2 md:px-2">
            <div className={`mb-5 inline-flex w-fit items-center rounded-full border px-3 py-1 text-xs font-semibold ${featuredLabel.tone}`}>
              {isKo ? featuredLabel.ko : featuredLabel.en}
            </div>
            <h2 className="text-2xl font-bold leading-tight text-white md:text-4xl">
              {getLocalizedProductTitle(featured, locale)}
            </h2>
            {featuredProject && (
              <p className="mt-4 text-sm font-medium text-gray-400">
                {featuredProject.name} {featuredProject.symbol ? `(${featuredProject.symbol})` : ''}
              </p>
            )}
            {featuredSummary && (
              <p className="mt-4 line-clamp-3 text-sm leading-6 text-gray-300 md:text-base">
                {featuredSummary}
              </p>
            )}
            <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-gray-500">
              {formatReportDate(featured, locale) && <span>{formatReportDate(featured, locale)}</span>}
              <span className="text-gray-700">/</span>
              <span>{isKo ? '리포트 보기' : 'Open report'} →</span>
            </div>
          </div>
        </Link>

        <div className="min-w-0">
          <div className="mb-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">
              {isKo ? '신규 발행 리포트' : 'Newly Published Reports'}
            </p>
            <h3 className="mt-2 text-2xl font-bold text-white">
              {isKo ? '실제 표지로 보는 최신 분석' : 'Latest analysis with real covers'}
            </h3>
          </div>

          <div className="grid gap-3">
            {secondaryReports.map((report) => {
              const product = getProduct(report)
              const label = reportTypeLabels[report.report_type] ?? reportTypeLabels.forensic

              return (
                <Link
                  key={report.id}
                  href={getReportHref(report, locale)}
                  className="group grid grid-cols-[76px_minmax(0,1fr)] gap-4 rounded-lg border border-white/10 bg-white/[0.025] p-3 transition-colors hover:border-white/20 hover:bg-white/[0.045]"
                >
                  <div className="relative aspect-[4/5] overflow-hidden rounded-md bg-gray-900">
                    <Image
                      src={product?.cover_image_url ?? ''}
                      alt={getLocalizedProductTitle(report, locale)}
                      fill
                      sizes="76px"
                      className="object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                    />
                  </div>
                  <div className="min-w-0 self-center">
                    <div className={`mb-2 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${label.tone}`}>
                      {isKo ? label.ko : label.en}
                    </div>
                    <p className="line-clamp-2 text-sm font-semibold leading-5 text-white">
                      {getLocalizedProductTitle(report, locale)}
                    </p>
                    {formatReportDate(report, locale) && (
                      <p className="mt-1 text-xs text-gray-500">{formatReportDate(report, locale)}</p>
                    )}
                  </div>
                </Link>
              )
            })}
          </div>

          <Link
            href={`/${locale}/reports`}
            className="mt-5 inline-flex rounded-lg border border-white/10 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-white/20 hover:text-white"
          >
            {isKo ? '전체 리포트 보기' : 'View all reports'} →
          </Link>
        </div>
      </div>
    </section>
  )
}
