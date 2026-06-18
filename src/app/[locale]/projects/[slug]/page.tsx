import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { CSSProperties } from 'react'

import { getShowcasePreview, type ReportWithCover } from '@/lib/latest-report-showcase'
import { getLocalizedMarketingContent } from '@/lib/report-marketing-content'
import { getMatchingProjectReportAliasIds, type ProjectReportAvailabilityCandidate } from '@/lib/report-availability'
import { getLocalizedCardSummary } from '@/lib/report-summary'
import { pickLocaleReport, reportSupportsLocale } from '@/lib/report-locale'
import {
  buildReportVersionHref,
  getReportVersionLabel,
  pickLatestReport,
  sortReportsLatestFirst,
} from '@/lib/report-versioning'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import type { ProjectReport, ReportType, TrackedProject } from '@/lib/types'

export const dynamic = 'force-dynamic'
export const revalidate = 0

interface Props {
  params: Promise<{ locale: string; slug: string }>
}

const localeDateMap: Record<string, string> = {
  en: 'en-US', ko: 'ko-KR', ja: 'ja-JP', zh: 'zh-CN',
  fr: 'fr-FR', es: 'es-ES', de: 'de-DE',
}

const REPORT_TYPE_THEME: Record<ReportType, {
  badgeBg: string
  badgeText: string
  badgeBorder: string
  cardBorder: string
  hoverBorder: string
  labelKo: string
  labelEn: string
  emoji: string
}> = {
  econ: {
    badgeBg: 'bg-blue-500/15',
    badgeText: 'text-blue-400',
    badgeBorder: 'border-blue-500/30',
    cardBorder: 'border-blue-500/15',
    hoverBorder: 'hover:border-blue-500/40',
    labelKo: 'ECON',
    labelEn: 'ECON',
    emoji: '📊',
  },
  maturity: {
    badgeBg: 'bg-green-500/15',
    badgeText: 'text-green-400',
    badgeBorder: 'border-green-500/30',
    cardBorder: 'border-green-500/15',
    hoverBorder: 'hover:border-green-500/40',
    labelKo: 'MAT',
    labelEn: 'MAT',
    emoji: '🌱',
  },
  forensic: {
    badgeBg: 'bg-red-500/15',
    badgeText: 'text-red-400',
    badgeBorder: 'border-red-500/30',
    cardBorder: 'border-red-500/15',
    hoverBorder: 'hover:border-red-500/40',
    labelKo: 'FOR',
    labelEn: 'FOR',
    emoji: '🔍',
  },
}

const REPORT_TYPE_ROUTE: Record<ReportType, string> = {
  econ: 'econ',
  maturity: 'maturity',
  forensic: 'forensic',
}

export function buildReportHref(locale: string, slug: string, reportType: ReportType): string {
  if (reportType === 'forensic') {
    return `/${locale}/reports/forensic/${slug}`
  }
  return `/${locale}/reports/${slug}/${REPORT_TYPE_ROUTE[reportType]}`
}

const REPORT_TYPE_DEFAULT_LABEL: Record<ReportType, { ko: string; en: string }> = {
  econ: { ko: '경제 분석', en: 'Economic Analysis' },
  maturity: { ko: '성숙도 평가', en: 'Maturity Assessment' },
  forensic: { ko: '포렌식 분석', en: 'Forensic Analysis' },
}

function formatMarketCap(value: number | null | undefined): string | null {
  if (value == null || value <= 0) return null
  if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
  if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`
  return `$${value.toFixed(0)}`
}

function pickLocalizedTitle(report: ProjectReport, locale: string, symbol: string): string {
  const direct = report[`title_${locale}` as keyof ProjectReport] as string | undefined
  if (direct) return direct
  if (locale === 'en' && report.title_en) return report.title_en
  const fallback = REPORT_TYPE_DEFAULT_LABEL[report.report_type]
  const label = locale === 'ko' ? fallback.ko : fallback.en
  return `${symbol} ${label}`
}

function pickLocalizedSummary(report: ProjectReport, locale: string): string | null {
  return getLocalizedCardSummary(report, locale) || null
}

function reportBelongsToLocale(report: ProjectReport, locale: string): boolean {
  return reportSupportsLocale(report, locale)
}

/**
 * Pick one report row per report type. The project page is an availability
 * index, so PDF/Drive-only legacy rows are still valid cards; the detail page
 * handles slide HTML first and then PDF fallback.
 */
export function selectReportsByType(
  reports: ProjectReport[],
  locale: string,
): Map<ReportType, ProjectReport> {
  const byType = new Map<ReportType, ProjectReport[]>()
  for (const report of reports) {
    const list = byType.get(report.report_type) || []
    list.push(report)
    byType.set(report.report_type, list)
  }

  const selected = new Map<ReportType, ProjectReport>()
  for (const [type, list] of byType.entries()) {
    const localeList = list.filter((report) => reportBelongsToLocale(report, locale))
    const latest = pickLatestReport(localeList)
    const eligible = latest
      ? sortReportsLatestFirst(
          localeList.filter((report) => report.version === latest.version),
        )
      : []
    const pick = pickLocaleReport(eligible, locale)
    if (pick) selected.set(type, pick)
  }
  return selected
}

export function buildReportHistoryByType(
  reports: ProjectReport[],
  selectedReports: Map<ReportType, ProjectReport>,
  locale: string,
): Map<ReportType, ProjectReport[]> {
  const history = new Map<ReportType, ProjectReport[]>()

  for (const type of REPORT_TYPE_ORDER) {
    const selected = selectedReports.get(type)
    const rows = sortReportsLatestFirst(
      reports.filter((report) => (
        report.report_type === type
        && Number(report.version || 0) < Number(selected?.version || 0)
        && reportBelongsToLocale(report, locale)
      )),
    )
    if (rows.length > 0) history.set(type, rows)
  }

  return history
}

const REPORT_TYPE_ORDER: ReportType[] = ['econ', 'maturity', 'forensic']
const PROJECT_HEADER_FALLBACK_IMAGE = '/images/score-header-bg.png'

export function getProjectDetailHeaderStyle(
  reports: ReportWithCover[],
  locale: string,
): CSSProperties {
  const previewUrl = reports
    .map((report) => getShowcasePreview(report, locale).url)
    .find((url) => typeof url === 'string' && url.trim().length > 0)
    || PROJECT_HEADER_FALLBACK_IMAGE

  return {
    backgroundImage: `linear-gradient(118deg, rgba(2, 6, 23, 0.9) 9%, rgba(2, 6, 23, 0.58) 46%, rgba(2, 6, 23, 0.9) 100%), url('${previewUrl}')`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
  }
}

export default async function ProjectDetailPage({ params }: Props) {
  const { locale, slug } = await params
  const supabase = await createServerSupabaseClient()
  const isKo = locale === 'ko'

  const { data: project } = await supabase
    .from('tracked_projects')
    .select('*')
    .eq('slug', slug)
    .single<TrackedProject>()

  if (!project || (project.status !== 'active' && project.status !== 'monitoring_only')) {
    notFound()
  }

  const { data: aliasCandidatesRaw } = await supabase
    .from('tracked_projects')
    .select('id, name, slug, symbol, coingecko_id, cmc_id, aliases')
    .in('status', ['active', 'monitoring_only'])

  const reportProjectIds = getMatchingProjectReportAliasIds(
    project as ProjectReportAvailabilityCandidate,
    (aliasCandidatesRaw || []) as ProjectReportAvailabilityCandidate[],
  )

  const { data: reportsRaw } = await supabase
    .from('project_reports')
    .select(`
      *,
      product:products(
        id,
        slug,
        title_en,
        title_ko,
        title_fr,
        title_es,
        title_de,
        title_ja,
        title_zh,
        cover_image_url,
        published_at
      )
    `)
    .in('project_id', reportProjectIds.length > 0 ? reportProjectIds : [project.id])
    .in('status', ['published', 'in_review'])
    .order('is_latest', { ascending: false })
    .order('updated_at', { ascending: false })

  const reports = (reportsRaw || []) as ReportWithCover[]
  const reportsByType = selectReportsByType(reports, locale)
  const historyByType = buildReportHistoryByType(reports, reportsByType, locale)
  const orderedReports = REPORT_TYPE_ORDER
    .map((type) => reportsByType.get(type))
    .filter((r): r is ProjectReport => Boolean(r))

  const marketCap = formatMarketCap(project.market_cap_usd)
  const dateLocale = localeDateMap[locale] || 'en-US'

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <section
        className="relative mb-12 overflow-hidden rounded-2xl border border-white/10 bg-slate-950 bg-cover bg-center px-6 py-8 shadow-2xl shadow-black/30 sm:px-8 sm:py-10"
        style={getProjectDetailHeaderStyle(reports, locale)}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.08),transparent_36%)]" />
        <div className="relative">
          <nav className="flex items-center gap-2 text-sm text-slate-300/75 mb-6">
            <Link href={`/${locale}`} className="transition-colors hover:text-cyan-200">
              {isKo ? '홈' : 'Home'}
            </Link>
            <span>/</span>
            <Link href={`/${locale}/score`} className="transition-colors hover:text-cyan-200">
              {isKo ? '리포트' : 'Reports'}
            </Link>
            <span>/</span>
            <span className="text-white">{project.name}</span>
          </nav>

          <div className="flex flex-wrap items-center gap-2 mb-4">
            {project.category && (
              <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-cyan-400/12 text-cyan-200 border border-cyan-300/20 backdrop-blur-sm">
                {project.category}
              </span>
            )}
            {project.chain && (
              <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-slate-950/20 text-slate-200 border border-white/10 backdrop-blur-sm">
                {project.chain}
              </span>
            )}
          </div>

          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="min-w-0 max-w-3xl">
              <div className="flex flex-wrap items-baseline gap-3">
                <h1 className="break-words text-4xl font-bold text-white drop-shadow-[0_2px_18px_rgba(0,0,0,0.84)] sm:text-5xl">
                  {project.name}
                </h1>
                <span className="text-xl text-slate-300/80 font-mono uppercase">{project.symbol}</span>
              </div>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-200/90 drop-shadow-[0_2px_12px_rgba(0,0,0,0.76)]">
                {isKo
                  ? '발행된 ECON, MAT, FOR 보고서와 최신 프로젝트 인사이트를 한 곳에서 확인하세요.'
                  : 'Review published ECON, MAT, and FOR reports with the latest project intelligence in one place.'}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:min-w-[min(100%,34rem)]">
              {marketCap && (
                <div className="rounded-lg border border-white/10 bg-slate-950/12 px-4 py-3 backdrop-blur-[1.5px]">
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-300/72">
                    {isKo ? '시가총액' : 'Market Cap'}
                  </div>
                  <div className="mt-1 text-lg font-semibold text-white font-mono">{marketCap}</div>
                </div>
              )}
              {project.maturity_score != null && (
                <div className="rounded-lg border border-white/10 bg-slate-950/12 px-4 py-3 backdrop-blur-[1.5px]">
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-300/72">
                    {isKo ? '성숙도 점수' : 'Maturity Score'}
                  </div>
                  <div className="mt-1 text-lg font-semibold text-white">
                    {Number(project.maturity_score).toFixed(1)}
                    {project.maturity_stage && (
                      <span className="ml-2 text-sm text-slate-300/80 font-normal">
                        {project.maturity_stage}
                      </span>
                    )}
                  </div>
                </div>
              )}
              {project.website_url && (
                <a
                  href={project.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-white/10 bg-slate-950/12 px-4 py-3 backdrop-blur-[1.5px] transition-colors hover:bg-slate-950/24"
                >
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-300/72">
                    {isKo ? '웹사이트' : 'Website'}
                  </div>
                  <div className="mt-1 truncate text-sm font-medium text-cyan-200">
                    {project.website_url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                    <span className="ml-1">↗</span>
                  </div>
                </a>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Reports Section */}
      <section>
        <h2 className="text-2xl font-bold text-white mb-6">
          {isKo ? '발행된 보고서' : 'Published Reports'}
        </h2>

        {orderedReports.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {orderedReports.map((report) => {
              const theme = REPORT_TYPE_THEME[report.report_type]
              const typeLabel = isKo ? theme.labelKo : theme.labelEn
              const title = pickLocalizedTitle(report, locale, project.symbol)
              const summary = pickLocalizedSummary(report, locale)
              const marketingContent = getLocalizedMarketingContent(report, locale, summary)
              const href = buildReportHref(locale, project.slug, report.report_type)
              const history = historyByType.get(report.report_type) || []
              const publishedAt = report.published_at
                ? new Date(report.published_at).toLocaleDateString(dateLocale, {
                    year: 'numeric', month: 'short', day: 'numeric',
                  })
                : null

              return (
                <div
                  key={report.id}
                  className={`relative group flex flex-col p-6 rounded-2xl bg-white/[0.03] border ${theme.cardBorder} ${theme.hoverBorder} hover:bg-white/[0.05] transition-all`}
                >
                  {/* Type chip - top right */}
                  <span
                    className={`absolute top-4 right-4 px-2.5 py-1 rounded-md text-[11px] font-bold uppercase ${theme.badgeBg} ${theme.badgeText} border ${theme.badgeBorder}`}
                  >
                    {theme.emoji} {typeLabel}
                  </span>

                  {/* Title */}
                  <Link href={href}>
                    <h3 className="text-lg font-semibold text-white mb-3 pr-20 line-clamp-2 hover:text-indigo-300 transition-colors">
                      {title}
                    </h3>
                  </Link>

                  {/* Summary */}
                  {summary && (
                    <p className="text-sm text-gray-400 leading-relaxed mb-6 line-clamp-3 flex-1">
                      {summary}
                    </p>
                  )}

                  {marketingContent && (
                    <div className="mb-6 rounded-xl border border-white/10 bg-gray-950/40 px-4 py-3">
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500">
                        {isKo ? '투자 관점' : 'Investment View'}
                      </p>
                      <p className="line-clamp-3 text-sm leading-relaxed text-gray-300">
                        {marketingContent}
                      </p>
                    </div>
                  )}

                  {/* Footer */}
                  <div className="flex items-center justify-between text-xs text-gray-500 pt-4 border-t border-white/5 mt-auto">
                    <span>{publishedAt || '—'}</span>
                    <span className="font-mono">v{report.version}</span>
                  </div>

                  {history.length > 0 && (
                    <div className="mt-4 border-t border-white/5 pt-3">
                      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-gray-600">
                        {isKo ? '이전 버전' : 'Previous Versions'}
                      </p>
                      <div className="flex flex-col gap-1.5">
                        {history.map((item) => {
                          const label = getReportVersionLabel(item)
                          return (
                            <Link
                              key={item.id}
                              href={buildReportVersionHref({
                                baseHref: href,
                                version: label.version,
                                language: label.language,
                                reportType: label.reportType,
                              })}
                              className="rounded-md border border-white/10 bg-black/10 px-2.5 py-1 text-[11px] text-gray-500 transition-colors hover:border-indigo-500/30 hover:text-indigo-300"
                            >
                              {new Date(label.date || item.created_at).toLocaleDateString(dateLocale, {
                                year: 'numeric', month: 'short', day: 'numeric',
                              })} · v{label.version} · {label.language.toUpperCase()} · {label.reportType.toUpperCase()}
                            </Link>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-16 rounded-2xl bg-white/[0.03] border border-white/5">
            <div className="text-5xl mb-4">📭</div>
            <p className="text-gray-400 text-base">
              {isKo
                ? '아직 발행된 보고서가 없습니다'
                : 'No reports have been published yet'}
            </p>
            <p className="text-gray-600 text-sm mt-2">
              {isKo
                ? '새 보고서가 발행되면 이곳에 표시됩니다.'
                : 'New reports will appear here once published.'}
            </p>
          </div>
        )}
      </section>
    </div>
  )
}
