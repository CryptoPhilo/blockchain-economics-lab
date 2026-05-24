'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { reportSupportsLocale } from '@/lib/report-locale'
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

function getProduct(report: ReportWithCover) {
  return Array.isArray(report.product) ? report.product[0] : report.product
}

export function hasReportCover(report: ReportWithCover) {
  return Boolean(getProduct(report)?.cover_image_url?.trim())
}

export function isPublishedReportCoverCandidate(report: ReportWithCover, locale: string) {
  return report.status === 'published' && reportSupportsLocale(report, locale) && hasReportCover(report)
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
  const coverReports = useMemo(
    () => reports.filter((report) => isPublishedReportCoverCandidate(report, locale)).slice(0, 8),
    [reports, locale],
  )
  const [activeIndex, setActiveIndex] = useState(0)
  const featured = coverReports[activeIndex] ?? coverReports[0]

  if (!featured) return null

  const isKo = locale === 'ko'
  const featuredProduct = getProduct(featured)
  const featuredProject = featured.tracked_projects ?? featured.project
  const featuredLabel = reportTypeLabels[featured.report_type] ?? reportTypeLabels.forensic
  const featuredSummary = getLocalizedSummary(featured, locale)
  const hasMultipleReports = coverReports.length > 1
  const goToPrevious = () => setActiveIndex((index) => (index === 0 ? coverReports.length - 1 : index - 1))
  const goToNext = () => setActiveIndex((index) => (index + 1) % coverReports.length)

  return (
    <section className="bg-gray-950 px-6 pb-16 pt-10 md:pb-20 md:pt-14">
      <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[minmax(0,0.86fr)_minmax(360px,1.14fr)] lg:items-center">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">
            {isKo ? '새로 발행된 보고서' : 'Newly Published Reports'}
          </p>
          <h1 className="mt-4 text-4xl font-bold leading-tight text-white md:text-6xl">
            {isKo ? '최신 ECON, MAT, FOR 리포트' : 'Latest ECON, MAT, and FOR Reports'}
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-gray-400 md:text-lg">
            {isKo
              ? '새로 발행된 리포트 표지를 한 장씩 크게 확인하세요.'
              : 'Browse newly published report covers one at a time.'}
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href={getReportHref(featured, locale)}
              className="inline-flex rounded-lg bg-white px-5 py-3 text-sm font-semibold text-gray-950 transition-colors hover:bg-gray-200"
            >
              {isKo ? '현재 리포트 보기' : 'Open current report'}
            </Link>
            <Link
              href={`/${locale}/reports`}
              className="inline-flex rounded-lg border border-white/15 px-5 py-3 text-sm font-semibold text-gray-200 transition-colors hover:border-white/30 hover:text-white"
            >
              {isKo ? '전체 리포트 보기' : 'View all reports'}
            </Link>
          </div>
        </div>

        <div className="min-w-0">
          <div className="relative overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]">
            <div
              className="flex transition-transform duration-500 ease-out"
              style={{ transform: `translateX(-${activeIndex * 100}%)` }}
            >
              {coverReports.map((report, index) => {
                const product = getProduct(report)
                const project = report.tracked_projects ?? report.project
                const label = reportTypeLabels[report.report_type] ?? reportTypeLabels.forensic
                const title = getLocalizedProductTitle(report, locale)

                return (
                  <Link
                    key={report.id}
                    href={getReportHref(report, locale)}
                    className="group grid min-w-full gap-5 p-4 md:grid-cols-[minmax(260px,0.78fr)_minmax(0,1fr)] md:p-5"
                    aria-hidden={index !== activeIndex}
                    tabIndex={index === activeIndex ? 0 : -1}
                  >
                    <div className="relative aspect-[4/5] overflow-hidden rounded-lg bg-gray-900 md:min-h-[460px]">
                      <Image
                        src={product?.cover_image_url ?? ''}
                        alt={title}
                        fill
                        sizes="(min-width: 1024px) 460px, (min-width: 768px) 42vw, 92vw"
                        className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                        priority={index === 0}
                      />
                    </div>
                    <div className="flex min-w-0 flex-col justify-center px-1 py-2 md:px-3">
                      <div className={`mb-5 inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold ${label.tone}`}>
                        {isKo ? label.ko : label.en}
                      </div>
                      <h2 className="text-2xl font-bold leading-tight text-white md:text-4xl">{title}</h2>
                      {project && (
                        <p className="mt-4 text-sm font-medium text-gray-400">
                          {project.name} {project.symbol ? `(${project.symbol})` : ''}
                        </p>
                      )}
                      {getLocalizedSummary(report, locale) && (
                        <p className="mt-4 line-clamp-4 text-sm leading-6 text-gray-300 md:text-base">
                          {getLocalizedSummary(report, locale)}
                        </p>
                      )}
                      <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-gray-500">
                        {formatReportDate(report, locale) && <span>{formatReportDate(report, locale)}</span>}
                        <span className="text-gray-700">/</span>
                        <span>{isKo ? '리포트 보기' : 'Open report'} →</span>
                      </div>
                    </div>
                  </Link>
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
              {coverReports.map((report, index) => (
                <button
                  key={report.id}
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
