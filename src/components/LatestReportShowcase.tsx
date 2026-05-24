'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { reportSupportsLocale } from '@/lib/report-locale'
import { cleanCardSummary } from '@/lib/report-summary'
import { getLocalizedField, type Locale, type Product, type ProjectReport, type ReportType, type TrackedProject } from '@/lib/types'

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
  reports?: ReportWithCover[]
  products?: Product[]
  locale: string
}

const reportTypeLabels: Record<ReportType, { en: string; ko: string; tone: string }> = {
  econ: {
    en: 'ECON',
    ko: '경제',
    tone: 'border-blue-400/30 bg-blue-400/10 text-blue-200',
  },
  maturity: {
    en: 'MAT',
    ko: 'MAT',
    tone: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
  },
  forensic: {
    en: 'FOR',
    ko: 'FOR',
    tone: 'border-red-400/30 bg-red-400/10 text-red-200',
  },
}

const supportedCoverLocales = ['en', 'ko', 'fr', 'es', 'de', 'ja', 'zh'] as const

function getProduct(report: ReportWithCover) {
  return Array.isArray(report.product) ? report.product[0] : report.product
}

function hasNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

export function getReportCoverAsset(report: ReportWithCover) {
  const productCoverUrl = getProduct(report)?.cover_image_url
  return hasNonEmptyString(productCoverUrl)
    ? { type: 'image' as const, url: productCoverUrl.trim() }
    : null
}

export function getLocalizedCoverUrls(coverUrl: string, locale: string) {
  const trimmedUrl = coverUrl.trim()
  if (!trimmedUrl) return []

  const normalizedLocale = supportedCoverLocales.includes(locale as typeof supportedCoverLocales[number])
    ? locale
    : 'en'
  const localizedUrl = trimmedUrl.replace(
    /\/(en|ko|fr|es|de|ja|zh)-cover\.(png|jpe?g|webp)(?=($|[?#]))/i,
    `/${normalizedLocale}-cover.$2`,
  )

  return localizedUrl === trimmedUrl ? [trimmedUrl] : [localizedUrl, trimmedUrl]
}

export function hasReportCover(report: ReportWithCover) {
  return getReportCoverAsset(report) !== null
}

export function isPublishedReportCoverCandidate(report: ReportWithCover, locale: string) {
  return report.status === 'published' && reportSupportsLocale(report, locale) && getReportCoverAsset(report) !== null
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

type ShowcaseItem = {
  id: string
  href: string
  title: string
  summary: string
  coverUrls: string[]
  reportType: ReportType
  dateValue?: string | null
  projectName?: string
  projectSymbol?: string
}

function getProductReportType(product: Product): ReportType {
  if (product.report_type === 'maturity') return 'maturity'
  if (product.report_type === 'forensic') return 'forensic'
  return 'econ'
}

function getProductShowcaseItems(products: Product[] | undefined, locale: string): ShowcaseItem[] {
  if (!products?.length) return []

  return products
    .filter((product) => product.status === 'published' && product.type === 'single_report' && hasNonEmptyString(product.cover_image_url))
    .map((product) => ({
      id: product.id,
      href: `/${locale}/products/${product.slug}`,
      title: getLocalizedField(product, 'title', locale as Locale),
      summary: getLocalizedField(product, 'description', locale as Locale) ?? '',
      coverUrls: getLocalizedCoverUrls(product.cover_image_url!, locale),
      reportType: getProductReportType(product),
      dateValue: product.published_at ?? product.created_at,
    }))
    .slice(0, 8)
}

function getReportShowcaseItems(reports: ReportWithCover[] | undefined, locale: string): ShowcaseItem[] {
  if (!reports?.length) return []

  return reports
    .filter((report) => isPublishedReportCoverCandidate(report, locale))
    .map((report) => {
      const project = report.tracked_projects ?? report.project
      const title = getLocalizedProductTitle(report, locale)
      const coverAsset = getReportCoverAsset(report)

      return {
        id: report.id,
        href: getReportHref(report, locale),
        title,
        summary: getLocalizedSummary(report, locale),
        coverUrls: coverAsset?.url ? getLocalizedCoverUrls(coverAsset.url, locale) : [],
        reportType: report.report_type,
        dateValue: report.published_at ?? getProduct(report)?.published_at ?? report.updated_at ?? report.created_at,
        projectName: project?.name,
        projectSymbol: project?.symbol,
      }
    })
    .filter((item) => item.coverUrls.length > 0)
    .slice(0, 8)
}

function formatDateValue(dateValue: string | null | undefined, locale: string) {
  if (!dateValue) return null

  return new Intl.DateTimeFormat(locale === 'ko' ? 'ko-KR' : 'en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(dateValue))
}

function ReportCoverImage({
  urls,
  title,
  priority,
}: {
  urls: string[]
  title: string
  priority: boolean
}) {
  const [activeUrlIndex, setActiveUrlIndex] = useState(0)
  const activeUrl = urls[activeUrlIndex]

  if (!activeUrl) {
    return <div className="h-full w-full bg-gray-900" aria-hidden="true" />
  }

  return (
    <Image
      src={activeUrl}
      alt={title}
      fill
      sizes="100vw"
      className="object-cover transition-transform duration-700 group-hover:scale-[1.03]"
      priority={priority}
      unoptimized
      onError={() => setActiveUrlIndex((index) => index + 1)}
    />
  )
}

export default function LatestReportShowcase({ reports, products, locale }: LatestReportShowcaseProps) {
  const showcaseItems = useMemo(
    () => {
      const productItems = getProductShowcaseItems(products, locale)
      return productItems.length > 0 ? productItems : getReportShowcaseItems(reports, locale)
    },
    [products, reports, locale],
  )
  const [activeIndex, setActiveIndex] = useState(0)
  const featured = showcaseItems[activeIndex] ?? showcaseItems[0]

  if (!featured) return null

  const isKo = locale === 'ko'
  const hasMultipleReports = showcaseItems.length > 1
  const goToPrevious = () => setActiveIndex((index) => (index === 0 ? showcaseItems.length - 1 : index - 1))
  const goToNext = () => setActiveIndex((index) => (index + 1) % showcaseItems.length)

  return (
    <section className="bg-gray-950 px-4 pb-10 pt-8 sm:px-6 md:pb-14 md:pt-10">
      <div className="mx-auto max-w-6xl">
        <div className="min-w-0">
          <div className="relative overflow-hidden rounded-xl border border-white/10 bg-gray-950 shadow-2xl shadow-black/30">
            <div
              className="flex transition-transform duration-500 ease-out"
              style={{ transform: `translateX(-${activeIndex * 100}%)` }}
            >
              {showcaseItems.map((item, index) => {
                const label = reportTypeLabels[item.reportType] ?? reportTypeLabels.forensic

                return (
                  <div
                    key={item.id}
                    className="group relative block min-h-[620px] min-w-full overflow-hidden md:min-h-[680px]"
                    aria-hidden={index !== activeIndex}
                  >
                    <ReportCoverImage key={item.coverUrls.join('|')} urls={item.coverUrls} title={item.title} priority={index === 0} />
                    <div className="absolute inset-0 bg-black/35" aria-hidden="true" />
                    <div className="absolute inset-0 bg-gradient-to-r from-black via-black/75 to-black/20" aria-hidden="true" />
                    <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent" aria-hidden="true" />
                    <div className="relative z-10 flex min-h-[620px] max-w-3xl flex-col justify-end px-6 py-8 sm:px-10 md:min-h-[680px] md:px-14 md:py-12">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-300">
                        {isKo ? '새로 발행된 보고서' : 'Newly Published Reports'}
                      </p>
                      <h1 className="mt-4 max-w-2xl text-4xl font-bold leading-tight text-white md:text-6xl">
                        {isKo ? '최신 ECON, MAT, FOR 리포트' : 'Latest ECON, MAT, and FOR Reports'}
                      </h1>
                      <div className={`mt-8 inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold ${label.tone}`}>
                        {isKo ? label.ko : label.en}
                      </div>
                      <h2 className="mt-5 max-w-xl text-2xl font-bold leading-tight text-white md:text-4xl">{item.title}</h2>
                      {item.projectName && (
                        <p className="mt-4 text-sm font-medium text-gray-400">
                          {item.projectName} {item.projectSymbol ? `(${item.projectSymbol})` : ''}
                        </p>
                      )}
                      {item.summary && (
                        <p className="mt-4 max-w-xl line-clamp-3 text-sm leading-6 text-gray-300 md:text-base">
                          {item.summary}
                        </p>
                      )}
                      <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-gray-400">
                        {formatDateValue(item.dateValue, locale) && <span>{formatDateValue(item.dateValue, locale)}</span>}
                        <span className="text-gray-600">/</span>
                        <span>{isKo ? '리포트 보기' : 'Open report'} →</span>
                      </div>
                      <div className="mt-8 flex flex-wrap items-center gap-3">
                        <Link
                          href={item.href}
                          tabIndex={index === activeIndex ? 0 : -1}
                          className="inline-flex rounded-lg bg-white px-5 py-3 text-sm font-semibold text-gray-950 transition-colors hover:bg-gray-200"
                        >
                          {isKo ? '현재 리포트 보기' : 'Open current report'}
                        </Link>
                        <Link
                          href={`/${locale}/reports`}
                          tabIndex={index === activeIndex ? 0 : -1}
                          className="inline-flex rounded-lg border border-white/20 px-5 py-3 text-sm font-semibold text-gray-100 transition-colors hover:border-white/40 hover:text-white"
                        >
                          {isKo ? '전체 리포트 보기' : 'View all reports'}
                        </Link>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {hasMultipleReports && (
              <div className="absolute inset-x-4 top-1/2 flex -translate-y-1/2 justify-between">
                <button
                  type="button"
                  onClick={goToPrevious}
                  className="grid h-10 w-10 place-items-center rounded-full border border-white/15 bg-gray-950/80 text-white transition-colors hover:border-white/30"
                  aria-label={isKo ? '이전 리포트' : 'Previous report'}
                >
                  <ChevronLeft size={20} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={goToNext}
                  className="grid h-10 w-10 place-items-center rounded-full border border-white/15 bg-gray-950/80 text-white transition-colors hover:border-white/30"
                  aria-label={isKo ? '다음 리포트' : 'Next report'}
                >
                  <ChevronRight size={20} aria-hidden="true" />
                </button>
              </div>
            )}
          </div>

          {hasMultipleReports && (
            <div className="mt-5 flex justify-center gap-2">
              {showcaseItems.map((item, index) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveIndex(index)}
                  className={`h-2.5 rounded-full transition-all ${
                    index === activeIndex ? 'w-8 bg-white' : 'w-2.5 bg-white/25 hover:bg-white/45'
                  }`}
                  aria-label={isKo ? `${index + 1}번째 리포트 보기` : `Show report ${index + 1}`}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
