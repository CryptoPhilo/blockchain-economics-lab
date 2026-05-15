import Link from 'next/link'
import { notFound } from 'next/navigation'

import { getLocalizedMarketingContent } from '@/lib/report-marketing-content'
import { cleanCardSummary } from '@/lib/report-summary'
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
  const direct = report[`card_summary_${locale}` as keyof ProjectReport] as string | undefined
  if (direct) return cleanCardSummary(direct)
  if (locale === 'en' && report.card_summary_en) return cleanCardSummary(report.card_summary_en)
  return null
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
    const latest = pickLatestReport(list)
    const eligible = latest
      ? sortReportsLatestFirst(
          list.filter((report) => report.version === latest.version && reportSupportsLocale(report, locale)),
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
        && reportSupportsLocale(report, locale)
      )),
    )
    if (rows.length > 0) history.set(type, rows)
  }

  return history
}

const REPORT_TYPE_ORDER: ReportType[] = ['econ', 'maturity', 'forensic']

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

  const { data: reportsRaw } = await supabase
    .from('project_reports')
    .select('*')
    .eq('project_id', project.id)
    .in('status', ['published', 'in_review'])
    .order('is_latest', { ascending: false })
    .order('updated_at', { ascending: false })

  const reports = (reportsRaw || []) as ProjectReport[]
  const reportsByType = selectReportsByType(reports, locale)
  const historyByType = buildReportHistoryByType(reports, reportsByType, locale)
  const orderedReports = REPORT_TYPE_ORDER
    .map((type) => reportsByType.get(type))
    .filter((r): r is ProjectReport => Boolean(r))

  const marketCap = formatMarketCap(project.market_cap_usd)
  const dateLocale = localeDateMap[locale] || 'en-US'

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-gray-500 mb-8">
        <Link href={`/${locale}`} className="hover:text-indigo-400 transition-colors">
          {isKo ? '홈' : 'Home'}
        </Link>
        <span>/</span>
        <Link href={`/${locale}/score`} className="hover:text-indigo-400 transition-colors">
          {isKo ? '리포트' : 'Reports'}
        </Link>
        <span>/</span>
        <span className="text-gray-300">{project.name}</span>
      </nav>

      {/* Header */}
      <header className="mb-12">
        <div className="flex flex-wrap items-center gap-2 mb-4">
          {project.category && (
            <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
              {project.category}
            </span>
          )}
          {project.chain && (
            <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-white/5 text-gray-400 border border-white/10">
              {project.chain}
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-baseline gap-3 mb-6">
          <h1 className="text-4xl md:text-5xl font-bold text-white">{project.name}</h1>
          <span className="text-xl text-gray-500 font-mono uppercase">{project.symbol}</span>
        </div>

        <div className="flex flex-wrap gap-4">
          {marketCap && (
            <div className="px-5 py-3 rounded-xl bg-white/[0.03] border border-white/5">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                {isKo ? '시가총액' : 'Market Cap'}
              </div>
              <div className="text-lg font-semibold text-white font-mono">{marketCap}</div>
            </div>
          )}
          {project.maturity_score != null && (
            <div className="px-5 py-3 rounded-xl bg-white/[0.03] border border-white/5">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                {isKo ? '성숙도 점수' : 'Maturity Score'}
              </div>
              <div className="text-lg font-semibold text-white">
                {Number(project.maturity_score).toFixed(1)}
                {project.maturity_stage && (
                  <span className="ml-2 text-sm text-gray-400 font-normal">
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
              className="px-5 py-3 rounded-xl bg-white/[0.03] border border-white/5 hover:bg-white/[0.06] hover:border-white/10 transition-all"
            >
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                {isKo ? '웹사이트' : 'Website'}
              </div>
              <div className="text-sm font-medium text-indigo-400 truncate max-w-[220px]">
                {project.website_url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                <span className="ml-1">↗</span>
              </div>
            </a>
          )}
        </div>
      </header>

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
