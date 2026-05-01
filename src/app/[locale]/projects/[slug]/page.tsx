import Link from 'next/link'
import { notFound } from 'next/navigation'

import { cleanCardSummary } from '@/lib/report-summary'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import type { ProjectReport, ReportType, SupportedLanguage, TrackedProject } from '@/lib/types'

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
  if (report.title_en) return report.title_en
  const fallback = REPORT_TYPE_DEFAULT_LABEL[report.report_type]
  const label = locale === 'ko' ? fallback.ko : fallback.en
  return `${symbol} ${label}`
}

function pickLocalizedSummary(report: ProjectReport, locale: string): string | null {
  const direct = report[`card_summary_${locale}` as keyof ProjectReport] as string | undefined
  if (direct) return cleanCardSummary(direct)
  if (report.card_summary_en) return cleanCardSummary(report.card_summary_en)
  return null
}

/**
 * Pick one report row per (report_type) using the language-scoped row strategy from BCE-1080.
 * Order of preference: current locale → en → ko → any other language.
 */
function selectReportsByType(
  reports: ProjectReport[],
  locale: string,
): Map<ReportType, ProjectReport> {
  const byType = new Map<ReportType, ProjectReport[]>()
  for (const report of reports) {
    const list = byType.get(report.report_type) || []
    list.push(report)
    byType.set(report.report_type, list)
  }

  const fallbackOrder: SupportedLanguage[] = [locale as SupportedLanguage, 'en', 'ko']
  const selected = new Map<ReportType, ProjectReport>()
  for (const [type, list] of byType.entries()) {
    let pick: ProjectReport | undefined
    for (const lang of fallbackOrder) {
      pick = list.find((r) => r.language === lang)
      if (pick) break
    }
    if (!pick) pick = list[0]
    if (pick) selected.set(type, pick)
  }
  return selected
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
    .eq('status', 'published')
    .not('published_at', 'is', null)
    .order('published_at', { ascending: false })

  const reports = (reportsRaw || []) as ProjectReport[]
  const reportsByType = selectReportsByType(reports, locale)
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
              const route = REPORT_TYPE_ROUTE[report.report_type]
              const href = `/${locale}/reports/${project.slug}/${route}`
              const publishedAt = report.published_at
                ? new Date(report.published_at).toLocaleDateString(dateLocale, {
                    year: 'numeric', month: 'short', day: 'numeric',
                  })
                : null

              return (
                <Link
                  key={report.id}
                  href={href}
                  className={`relative group flex flex-col p-6 rounded-2xl bg-white/[0.03] border ${theme.cardBorder} ${theme.hoverBorder} hover:bg-white/[0.05] transition-all`}
                >
                  {/* Type chip - top right */}
                  <span
                    className={`absolute top-4 right-4 px-2.5 py-1 rounded-md text-[11px] font-bold uppercase ${theme.badgeBg} ${theme.badgeText} border ${theme.badgeBorder}`}
                  >
                    {theme.emoji} {typeLabel}
                  </span>

                  {/* Title */}
                  <h3 className="text-lg font-semibold text-white mb-3 pr-20 line-clamp-2 group-hover:text-indigo-300 transition-colors">
                    {title}
                  </h3>

                  {/* Summary */}
                  {summary && (
                    <p className="text-sm text-gray-400 leading-relaxed mb-6 line-clamp-3 flex-1">
                      {summary}
                    </p>
                  )}

                  {/* Footer */}
                  <div className="flex items-center justify-between text-xs text-gray-500 pt-4 border-t border-white/5 mt-auto">
                    <span>{publishedAt || '—'}</span>
                    <span className="font-mono">v{report.version}</span>
                  </div>
                </Link>
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
