'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { reportHasSlideAssetForLocale, reportSupportsLocale } from '@/lib/report-locale'
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

const reportTypeLabels: Record<ReportType, { label: string; tone: string }> = {
  econ: {
    label: 'ECON',
    tone: 'border-blue-400/30 bg-blue-400/10 text-blue-200',
  },
  maturity: {
    label: 'MAT',
    tone: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
  },
  forensic: {
    label: 'FOR',
    tone: 'border-red-400/30 bg-red-400/10 text-red-200',
  },
}

const supportedCoverLocales = ['en', 'ko', 'fr', 'es', 'de', 'ja', 'zh'] as const
const requiredShowcaseCoverLocales = ['en', 'ko', 'ja', 'zh'] as const
const MIN_SHOWCASE_ITEMS = 4
const MAX_SHOWCASE_ITEMS = 8
const SHOWCASE_ROLL_INTERVAL_MS = 6000

function getProduct(report: ReportWithCover) {
  return Array.isArray(report.product) ? report.product[0] : report.product
}

function hasNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function uniqueStrings(values: string[]) {
  return [...new Set(values.filter((value) => value.trim().length > 0))]
}

function normalizeCoverLocale(locale: string) {
  return supportedCoverLocales.includes(locale as typeof supportedCoverLocales[number]) ? locale : 'en'
}

function getLocalizedReportCoverUrls(report: ReportWithCover, locale: string) {
  const coverUrls = report.cover_image_urls_by_lang ?? {}
  const normalizedLocale = normalizeCoverLocale(locale)
  return getLocalizedCoverUrlsByLang(coverUrls, normalizedLocale)
}

function getLocalizedCoverUrlsByLang(coverUrls: Record<string, string>, locale: string) {
  return uniqueStrings([
    coverUrls[locale] ?? '',
    coverUrls.en ?? '',
    ...Object.values(coverUrls),
  ].filter(hasNonEmptyString))
}

export function getReportCoverAsset(report: ReportWithCover) {
  const coverUrl = getReportCoverUrls(report, 'en')[0]
  return coverUrl ? { type: 'image' as const, url: coverUrl } : null
}

export function getReportCoverUrls(report: ReportWithCover, locale: string) {
  const productCoverUrl = getProduct(report)?.cover_image_url
  return uniqueStrings([
    ...getLocalizedReportCoverUrls(report, locale),
    ...(hasNonEmptyString(productCoverUrl) ? getLocalizedCoverUrls(productCoverUrl, locale) : []),
  ])
}

export function getLocalizedCoverUrls(coverUrl: string, locale: string) {
  const trimmedUrl = coverUrl.trim()
  if (!trimmedUrl) return []

  const normalizedLocale = normalizeCoverLocale(locale)
  const localizedUrl = trimmedUrl.replace(
    /\/(en|ko|fr|es|de|ja|zh)-cover\.(png|jpe?g|webp)(?=($|[?#]))/i,
    `/${normalizedLocale}-cover.$2`,
  )

  return localizedUrl === trimmedUrl ? [trimmedUrl] : [localizedUrl, trimmedUrl]
}

export function hasReportCover(report: ReportWithCover) {
  return getReportCoverAsset(report) !== null
}

export function hasRequiredShowcaseCoverLocales(report: ReportWithCover) {
  const coverUrls = report.cover_image_urls_by_lang ?? {}
  return hasRequiredShowcaseCoverUrlMap(coverUrls)
}

function hasRequiredShowcaseCoverUrlMap(coverUrls: Record<string, string>) {
  return requiredShowcaseCoverLocales.every((locale) => hasNonEmptyString(coverUrls[locale]))
}

export function isPublishedReportCoverCandidate(report: ReportWithCover, locale: string) {
  return report.status === 'published'
    && reportHasSlideAssetForLocale(report, locale)
    && hasRequiredShowcaseCoverLocales(report)
    && getReportCoverUrls(report, locale).length > 0
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
  const projectName = report.tracked_projects?.name ?? report.project?.name
  if (projectName?.trim()) return projectName

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

type ShowcaseCandidate = ShowcaseItem & {
  hasRequiredLocaleCovers: boolean
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

function getReportGroupKey(report: ReportWithCover) {
  const project = report.tracked_projects ?? report.project
  return [
    report.report_type,
    project?.slug ?? project?.id ?? report.project_id ?? 'unknown-project',
    report.version ?? 'latest',
  ].join(':')
}

function getReportSortTime(report: ReportWithCover) {
  return new Date(report.published_at ?? getProduct(report)?.published_at ?? report.updated_at ?? report.created_at ?? 0).getTime()
}

function mergeReportGroupCoverUrls(reports: ReportWithCover[]) {
  const coverUrls: Record<string, string> = {}
  for (const report of reports) {
    const reportCoverUrls = report.cover_image_urls_by_lang ?? {}
    for (const [language, url] of Object.entries(reportCoverUrls)) {
      if (!hasNonEmptyString(coverUrls[language]) && hasNonEmptyString(url)) {
        coverUrls[language] = url
      }
    }
  }
  return coverUrls
}

function pickLocalizedReportFromGroup(reports: ReportWithCover[], locale: string) {
  const availableReports = reports.filter((report) => reportHasSlideAssetForLocale(report, locale))
  return availableReports.find((report) => report.language === locale)
    ?? availableReports.find((report) => reportSupportsLocale(report, locale))
    ?? availableReports.find((report) => report.language === 'en')
    ?? availableReports[0]
    ?? reports[0]
}

export function getReportShowcaseItems(reports: ReportWithCover[] | undefined, locale: string): ShowcaseItem[] {
  if (!reports?.length) return []

  const groups = new Map<string, ReportWithCover[]>()
  for (const report of reports) {
    if (report.status !== 'published') continue
    const key = getReportGroupKey(report)
    groups.set(key, [...(groups.get(key) ?? []), report])
  }

  const candidates: ShowcaseCandidate[] = [...groups.values()]
    .map((group) => group.sort((a, b) => getReportSortTime(b) - getReportSortTime(a)))
    .filter((group) => group.some((report) => reportHasSlideAssetForLocale(report, locale)))
    .map((group) => {
      const report = pickLocalizedReportFromGroup(group, locale)
      const project = report.tracked_projects ?? report.project
      const title = getLocalizedProductTitle(report, locale)
      const coverUrlMap = mergeReportGroupCoverUrls(group)
      const coverUrls = getLocalizedCoverUrlsByLang(coverUrlMap, normalizeCoverLocale(locale))

      return {
        id: getReportGroupKey(report),
        href: getReportHref(report, locale),
        title,
        summary: getLocalizedSummary(report, locale),
        coverUrls,
        reportType: report.report_type,
        dateValue: group[0].published_at ?? getProduct(group[0])?.published_at ?? group[0].updated_at ?? group[0].created_at,
        projectName: project?.name,
        projectSymbol: project?.symbol,
        hasRequiredLocaleCovers: hasRequiredShowcaseCoverUrlMap(coverUrlMap),
      }
    })
    .filter((item) => item.coverUrls.length > 0)

  const completeCoverItems = candidates.filter((item) => item.hasRequiredLocaleCovers)
  const relaxedCoverItems = candidates.filter((item) => !item.hasRequiredLocaleCovers)
  const items = completeCoverItems.length >= MIN_SHOWCASE_ITEMS
    ? completeCoverItems
    : [...completeCoverItems, ...relaxedCoverItems]

  return items.slice(0, MAX_SHOWCASE_ITEMS)
}

function sortShowcaseItemsByDate(items: ShowcaseItem[]) {
  return [...items].sort((a, b) => (
    new Date(b.dateValue ?? 0).getTime() - new Date(a.dateValue ?? 0).getTime()
  ))
}

function getShowcaseDedupKey(item: ShowcaseItem) {
  return `${item.reportType}:${item.projectSymbol ?? item.projectName ?? item.title}`.toLowerCase()
}

function dedupeShowcaseItems(items: ShowcaseItem[]) {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = getShowcaseDedupKey(item)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
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
      const reportItems = getReportShowcaseItems(reports, locale)
      const productItems = getProductShowcaseItems(products, locale)
      const items = reportItems.length >= MIN_SHOWCASE_ITEMS
        ? reportItems
        : [...reportItems, ...productItems]
      return dedupeShowcaseItems(sortShowcaseItemsByDate(items)).slice(0, MAX_SHOWCASE_ITEMS)
    },
    [products, reports, locale],
  )
  const [activeIndex, setActiveIndex] = useState(0)
  const safeActiveIndex = showcaseItems.length > 0 ? activeIndex % showcaseItems.length : 0
  const featured = showcaseItems[safeActiveIndex] ?? showcaseItems[0]

  useEffect(() => {
    if (showcaseItems.length <= 1) return undefined

    const intervalId = window.setInterval(() => {
      setActiveIndex((index) => (index + 1) % showcaseItems.length)
    }, SHOWCASE_ROLL_INTERVAL_MS)

    return () => window.clearInterval(intervalId)
  }, [showcaseItems.length])

  if (!featured) return null

  const isKo = locale === 'ko'
  const hasMultipleReports = showcaseItems.length > 1
  const goToPrevious = () => setActiveIndex((index) => (index + showcaseItems.length - 1) % showcaseItems.length)
  const goToNext = () => setActiveIndex((index) => (index + 1) % showcaseItems.length)

  return (
    <section className="bg-gray-950 px-4 pb-10 pt-8 sm:px-6 md:pb-14 md:pt-10">
      <div className="mx-auto max-w-6xl">
        <div className="min-w-0">
          <div className="relative overflow-hidden rounded-xl border border-white/10 bg-gray-950 shadow-2xl shadow-black/30">
            <div
              className="flex transition-transform duration-1000 ease-out"
              style={{ transform: `translateX(-${safeActiveIndex * 100}%)` }}
            >
              {showcaseItems.map((item, index) => {
                const label = reportTypeLabels[item.reportType] ?? reportTypeLabels.forensic

                return (
                  <div
                    key={item.id}
                    className="group relative block min-h-[620px] min-w-full overflow-hidden md:min-h-[680px]"
                    aria-hidden={index !== safeActiveIndex}
                  >
                    <ReportCoverImage key={item.coverUrls.join('|')} urls={item.coverUrls} title={item.title} priority={index === 0} />
                    <div className="absolute inset-0 bg-black/20" aria-hidden="true" />
                    <div className="absolute inset-0 bg-gradient-to-r from-black/95 via-black/55 to-transparent" aria-hidden="true" />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/25 to-transparent" aria-hidden="true" />
                    <div className="relative z-10 flex min-h-[620px] max-w-3xl flex-col justify-end px-6 py-8 sm:px-10 md:min-h-[680px] md:px-14 md:py-12">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-300">
                        {isKo ? '새로 발행된 보고서' : 'Newly Published Reports'}
                      </p>
                      <h1 className="mt-4 max-w-2xl text-4xl font-bold leading-tight text-white md:text-6xl">
                        {isKo ? '최신 ECON, MAT, FOR 리포트' : 'Latest ECON, MAT, and FOR Reports'}
                      </h1>
                      <div className={`mt-8 inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold ${label.tone}`}>
                        {label.label}
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
                          tabIndex={index === safeActiveIndex ? 0 : -1}
                          className="inline-flex rounded-lg bg-white px-5 py-3 text-sm font-semibold text-gray-950 transition-colors hover:bg-gray-200"
                        >
                          {isKo ? '현재 리포트 보기' : 'Open current report'}
                        </Link>
                        <Link
                          href={`/${locale}/reports`}
                          tabIndex={index === safeActiveIndex ? 0 : -1}
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
                    index === safeActiveIndex ? 'w-8 bg-white' : 'w-2.5 bg-white/25 hover:bg-white/45'
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
