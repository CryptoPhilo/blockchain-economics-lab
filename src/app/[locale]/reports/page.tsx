import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import Link from 'next/link'
import type { ProjectReport } from '@/lib/types'
import { getLocalizedMarketingContent } from '@/lib/report-marketing-content'
import { buildReportVersionHref, getReportVersionLabel } from '@/lib/report-versioning'
import { prepareRapidChangeReports } from './reports-page-utils'
import { ProjectsRepository } from '@/lib/repositories/projects'

interface Props {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ page?: string; q?: string }>
}

const PAGE_SIZE = 20
const MAX_CMC_RANK = 500
const RAPID_CHANGE_REPORT_SELECT = `
  id,
  project_id,
  report_type,
  version,
  is_latest,
  status,
  language,
  assigned_at,
  published_at,
  source_modified_time,
  created_at,
  updated_at,
  trigger_reason,
  card_summary_en,
  card_summary_ko,
  card_summary_fr,
  card_summary_es,
  card_summary_de,
  card_summary_ja,
  card_summary_zh,
  marketing_content_by_lang,
  card_data,
  file_url,
  file_urls_by_lang,
  gdrive_url,
  gdrive_urls_by_lang,
  slide_html_urls_by_lang,
  title_en,
  title_ko,
  title_fr,
  title_es,
  title_de,
  title_ja,
  title_zh,
  translation_status,
  project:tracked_projects(id, name, slug, symbol, chain, category)
`

const LANG_NAMES: Record<string, string> = {
  en: 'English', ko: '한국어', ja: '日本語', zh: '中文',
  fr: 'Français', es: 'Español', de: 'Deutsch',
}

const FORENSIC_CONFIG = {
  color: 'bg-red-500/20 text-red-400 border-red-500/30',
  label: 'FOR',
  icon: '🔍'
} as const

type RapidChangeProject = NonNullable<ProjectReport['project']> & { cmc_rank?: number | null }
type RapidChangeReport = ProjectReport & { project?: RapidChangeProject }

function toTop500CmcRank(value: unknown): number | null {
  const rank = typeof value === 'number' ? value : Number(value)
  return Number.isInteger(rank) && rank >= 1 && rank <= MAX_CMC_RANK ? rank : null
}

function getProjectCmcRank(report: ProjectReport): number | null {
  return toTop500CmcRank((report.project as RapidChangeProject | undefined)?.cmc_rank)
}

function isFilenameDerivedForTitle(value: unknown): boolean {
  if (typeof value !== 'string') return false

  return /(?:^|\s)(?:FOR|FOF|for)\s+(?:ko|en|jp|ja|cn|zh)(?:\(\d+\))?$/i.test(value.trim())
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getLocalizedTitle(report: any, locale: string): string {
  const project = report.project
  const typeName = locale === 'ko' ? '포렌식 분석' : 'Forensic Analysis'
  const fallback = project?.name
    ? `${project.name} ${typeName}`
    : `${typeName} v${report.version}`
  const key = `title_${locale}`
  const localizedTitle = report[key]

  if (localizedTitle && !isFilenameDerivedForTitle(localizedTitle)) return localizedTitle
  if (report.title_en && !isFilenameDerivedForTitle(report.title_en)) return report.title_en

  return fallback
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

function formatRelativeTime(dateStr: string, locale: string): string {
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffMinutes = Math.floor(diffMs / (1000 * 60))

  if (diffMinutes < 60) {
    return locale === 'ko' ? `${diffMinutes}분 전` : `${diffMinutes}m ago`
  }
  if (diffHours < 24) {
    return locale === 'ko' ? `${diffHours}시간 전` : `${diffHours}h ago`
  }
  const diffDays = Math.floor(diffHours / 24)
  return locale === 'ko' ? `${diffDays}일 전` : `${diffDays}d ago`
}

function getRapidChangeTimestamp(report: ProjectReport): string | null {
  return report.source_modified_time || report.published_at || report.created_at || null
}

function getLocalizedSummary(report: ProjectReport, locale: string): string {
  const summaryByLang = report.card_data?.summary_by_lang
  const candidate =
    (summaryByLang && typeof summaryByLang === 'object'
      ? summaryByLang[locale]
      : undefined)
    ?? report[`card_summary_${locale}` as keyof ProjectReport]
    ?? (locale === 'en' ? report.card_summary_en : undefined)

  return typeof candidate === 'string' ? candidate : ''
}

function getRapidChangeReason(report: ProjectReport, locale: string): string {
  const triggerReason = report.trigger_reason?.trim()
  if (triggerReason) return triggerReason

  return getLocalizedSummary(report, locale).trim()
}

function hasLocalizedSlide(report: ProjectReport, locale: string): boolean {
  const urls = report.slide_html_urls_by_lang
  if (!urls || typeof urls !== 'object') return false
  const value = urls[locale]
  return typeof value === 'string' && value.trim().length > 0
}

export default async function ReportsPage({ params, searchParams }: Props) {
  const { locale } = await params
  const { page: pageStr, q: searchQuery } = await searchParams
  const supabase = await createServerSupabaseClient()
  const t = await getTranslations('reports')
  const currentPage = Math.max(1, parseInt(pageStr || '1', 10))
  const projectsRepository = new ProjectsRepository(supabase)

  const seventyTwoHoursAgo = new Date()
  seventyTwoHoursAgo.setHours(seventyTwoHoursAgo.getHours() - 72)

  const dataQuery = supabase
    .from('project_reports')
    .select(RAPID_CHANGE_REPORT_SELECT)
    .in('status', ['published', 'coming_soon', 'in_review'])
    .eq('report_type', 'forensic')
    .or(
      [
        `source_modified_time.gte.${seventyTwoHoursAgo.toISOString()}`,
        `and(source_modified_time.is.null,published_at.gte.${seventyTwoHoursAgo.toISOString()})`,
        `and(source_modified_time.is.null,published_at.is.null,created_at.gte.${seventyTwoHoursAgo.toISOString()})`,
      ].join(',')
    )
    .order('is_latest', { ascending: false })
    .order('updated_at', { ascending: false })
    .order('created_at', { ascending: false })

  const [{ data: rawReports }, marketSnapshotRows] = await Promise.all([
    dataQuery,
    projectsRepository.getLatestCmcRanks(MAX_CMC_RANK),
  ])
  const cmcRankBySlug = new Map(
    marketSnapshotRows
      .map((row) => [row.slug, toTop500CmcRank(row.cmc_rank)] as const)
      .filter((entry): entry is readonly [string, number] => entry[1] !== null)
  )
  const rankedReports = ((rawReports || []) as unknown as ProjectReport[])
    .map((report): RapidChangeReport => {
      const project = report.project
      if (!project) return report

      return {
        ...report,
        project: {
          ...project,
          cmc_rank: cmcRankBySlug.get(project.slug) ?? null,
        },
      }
    })
    .filter((report) => getProjectCmcRank(report) !== null)

  const {
    reports,
    historyByProject,
    totalCount,
    totalPages,
    currentPage: activePage,
  } = prepareRapidChangeReports({
    reports: rankedReports,
    locale,
    page: currentPage,
    pageSize: PAGE_SIZE,
    searchQuery,
  })

  function filterUrl(params: { page?: number; q?: string }) {
    const sp = new URLSearchParams()
    const pg = params.page !== undefined ? params.page : (params.q !== undefined ? 1 : activePage)
    const query = params.q !== undefined ? params.q : (searchQuery || '')
    if (pg > 1) sp.set('page', String(pg))
    if (query) sp.set('q', query)
    const qs = sp.toString()
    return `/${locale}/reports${qs ? `?${qs}` : ''}`
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-4xl font-bold mb-2">
          🚨 {locale === 'ko' ? '급변동 종목' : 'Rapid Change Alerts'}
        </h1>
        <p className="text-gray-400 mb-3">
          {locale === 'ko'
            ? '72시간 내에 발행된 포렌식(FOR) 보고서 - 긴급 시장 변화를 놓치지 마세요'
            : 'Forensic (FOR) reports published within 72 hours - Don\'t miss critical market changes'}
        </p>
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          <span className="animate-pulse">🔴</span>
          <span>
            {locale === 'ko'
              ? `실시간 업데이트 • ${totalCount || 0}건의 최신 보고서`
              : `Live Updates • ${totalCount || 0} Latest Reports`}
          </span>
        </div>
      </div>

      {/* Search Bar */}
      <div className="space-y-4 mb-8">
        <form action={`/${locale}/reports`} method="GET" className="flex gap-3">
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">🔍</span>
            <input
              type="text"
              name="q"
              defaultValue={searchQuery || ''}
              placeholder={locale === 'ko' ? '프로젝트명, 심볼로 검색...' : 'Search by project name or symbol...'}
              className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-red-500/20 text-white placeholder-gray-500 focus:outline-none focus:border-red-500/50 focus:ring-1 focus:ring-red-500/30"
            />
          </div>
          <button
            type="submit"
            className="px-6 py-3 bg-red-600 hover:bg-red-500 text-white font-medium rounded-xl transition-colors"
          >
            {locale === 'ko' ? '검색' : 'Search'}
          </button>
          {searchQuery && (
            <Link
              href={filterUrl({ q: '' })}
              className="px-4 py-3 bg-white/5 hover:bg-white/10 text-gray-400 rounded-xl transition-colors"
            >
              ✕
            </Link>
          )}
        </form>

        {searchQuery && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>{locale === 'ko' ? '검색 결과:' : 'Search:'}</span>
            <span className="px-2 py-0.5 rounded bg-white/5 text-gray-400">
              &quot;{searchQuery}&quot;
            </span>
            <Link href={`/${locale}/reports`} className="text-red-400 hover:text-red-300 ml-2">
              {locale === 'ko' ? '초기화' : 'Clear'}
            </Link>
            <span className="ml-auto text-gray-600">
              {totalCount || 0} {locale === 'ko' ? '건' : 'results'}
            </span>
          </div>
        )}
      </div>

      {/* Reports List */}
      {reports && reports.length > 0 ? (
        <div className="grid gap-4">
          {reports.map((report) => {
            const project = report.project
            const cmcRank = getProjectCmcRank(report)
            const config = FORENSIC_CONFIG
            const title = getLocalizedTitle(report, locale)
            const summary = getLocalizedSummary(report, locale)
            const rapidChangeReason = getRapidChangeReason(report, locale)
            const marketingContent = getLocalizedMarketingContent(report, locale, summary)
            const history = historyByProject.get(report.project_id) || []
            const hasReportViewer = hasLocalizedSlide(report, locale)

            const translationStatus = report.translation_status || {}
            const gdriveUrls = report.gdrive_urls_by_lang || {}
            const resolveUrl = (val: unknown): string | undefined => {
              if (typeof val === 'string') return val
              if (val && typeof val === 'object' && 'url' in val) return (val as { url: string }).url
              return undefined
            }
            const availableLangs = [...new Set([
              ...Object.keys(gdriveUrls),
              ...Object.entries(translationStatus)
                .filter(([, v]) => v === 'published')
                .map(([k]) => k)
            ])].sort()

            const reportTime = getRapidChangeTimestamp(report)
            const relativeTime = reportTime ? formatRelativeTime(reportTime, locale) : null

            return (
              <div
                key={report.id}
                className="relative flex flex-col gap-4 p-6 rounded-2xl bg-gradient-to-br from-red-500/5 via-white/[0.03] to-white/[0.03] border border-red-500/20 hover:border-red-500/40 transition-all hover:shadow-lg hover:shadow-red-500/10 scroll-mt-20"
              >
                {relativeTime && (
                  <div className="absolute top-4 right-4 px-2 py-1 rounded-full bg-red-500/20 text-red-400 text-xs font-semibold">
                    ⚡ {relativeTime}
                  </div>
                )}

                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                  <div className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase shrink-0 ${config.color} ring-1 ring-red-500/30`}>
                    {config.icon} {config.label}
                  </div>
                  <div className="flex-1 min-w-0 pr-20 sm:pr-0">
                    <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                      {project && (
                        <Link
                          href={`/${locale}/projects/${project.slug}`}
                          className="inline-flex items-center gap-1.5 hover:text-red-400 transition-colors font-medium"
                        >
                          <span>{project.name} ({project.symbol})</span>
                          {cmcRank !== null && (
                            <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-red-400 ring-1 ring-red-500/20">
                              CMC #{cmcRank}
                            </span>
                          )}
                        </Link>
                      )}
                      {project?.category && (
                        <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-600">{project.category}</span>
                      )}
                      <span>v{report.version}</span>
                      {reportTime && (
                        <span>{formatDate(reportTime)}</span>
                      )}
                    </div>
                  </div>

                  {!hasReportViewer ? (
                    <span className="px-4 py-2 bg-amber-500/10 text-amber-400 text-sm font-medium rounded-lg border border-amber-500/20 cursor-default shrink-0">
                      🔜 {locale === 'ko' ? '보고서 준비 중' : 'Report pending'}
                    </span>
                  ) : project ? (
                    <Link
                      href={buildReportVersionHref({
                        baseHref: `/${locale}/reports/forensic/${project.slug}`,
                        version: Number(report.version || 1),
                        language: locale,
                        reportType: 'forensic',
                      })}
                      className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 hover:text-red-300 text-sm font-medium rounded-lg transition-colors shrink-0 border border-red-500/30"
                    >
                      {locale === 'ko' ? '보고서 상세' : 'Report Details'} →
                    </Link>
                  ) : null}
                </div>

                {marketingContent && (
                  <div className="rounded-xl border border-red-500/15 bg-gray-950/40 px-4 py-3">
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500">
                      {locale === 'ko' ? '투자 관점' : 'Investment View'}
                    </p>
                    <p className="line-clamp-2 text-sm leading-relaxed text-gray-300">
                      {marketingContent}
                    </p>
                  </div>
                )}

                {rapidChangeReason && (
                  <div className="rounded-xl border border-amber-500/15 bg-amber-500/[0.04] px-4 py-3">
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-500/80">
                      {locale === 'ko' ? '감지 이유' : 'Detection Reason'}
                    </p>
                    <p className="line-clamp-2 text-sm leading-relaxed text-amber-100/85">
                      {rapidChangeReason}
                    </p>
                  </div>
                )}

                {availableLangs.length > 1 && (
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/5">
                    <span className="text-xs text-gray-600 mr-1">{t('languages')}:</span>
                    {availableLangs.map((lang) => {
                      const url = resolveUrl(gdriveUrls[lang])
                      const badge = (
                        <span
                          key={lang}
                          className={`px-2 py-0.5 rounded text-[11px] font-medium uppercase ${
                            lang === locale
                              ? 'bg-red-500/20 text-red-400 ring-1 ring-red-500/30'
                              : 'bg-white/5 text-gray-500 hover:bg-white/10'
                          }`}
                        >
                          {LANG_NAMES[lang] || lang}
                        </span>
                      )
                      if (url) {
                        return (
                          <a key={lang} href={url} target="_blank" rel="noopener noreferrer" className="hover:opacity-80">
                            {badge}
                          </a>
                        )
                      }
                      return badge
                    })}
                  </div>
                )}

                {history.length > 0 && project && (
                  <div className="pt-3 border-t border-white/5">
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-600">
                      {locale === 'ko' ? '이전 버전' : 'Previous Versions'}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {history.map((item) => {
                        const label = getReportVersionLabel(item)
                        return (
                          <Link
                            key={item.id}
                            href={buildReportVersionHref({
                              baseHref: `/${locale}/reports/forensic/${project.slug}`,
                              version: label.version,
                              language: label.language || null,
                              reportType: label.reportType,
                            })}
                            className="rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-gray-500 transition-colors hover:border-red-500/30 hover:text-red-300"
                          >
                            {formatDate(label.date || null)} · v{label.version} · {label.language.toUpperCase()} · {label.reportType.toUpperCase()}
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
        <div className="text-center py-20 rounded-2xl bg-white/[0.03] border border-white/5">
          <div className="text-6xl mb-4">✅</div>
          <p className="text-gray-400 text-lg mb-2">
            {locale === 'ko'
              ? '현재 72시간 내 발행된 FOR 보고서가 없습니다'
              : 'No FOR reports published within the last 72 hours'}
          </p>
          <p className="text-gray-600 text-sm">
            {locale === 'ko'
              ? '시장이 안정적입니다. 새 보고서가 발행되면 여기에 표시됩니다.'
              : 'The market is stable. New reports will appear here when published.'}
          </p>
          {searchQuery && (
            <Link href={`/${locale}/reports`} className="text-red-400 hover:text-red-300 mt-4 inline-block">
              {locale === 'ko' ? '필터 초기화' : 'Clear filters'} →
            </Link>
          )}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <nav className="flex items-center justify-center gap-2 mt-10">
          {activePage > 1 && (
            <Link
              href={filterUrl({ page: activePage - 1 })}
              className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 text-sm transition-colors"
            >
              ← {locale === 'ko' ? '이전' : 'Prev'}
            </Link>
          )}
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter((p) => p === 1 || p === totalPages || Math.abs(p - activePage) <= 2)
            .reduce<(number | string)[]>((acc, p, i, arr) => {
              if (i > 0 && p - (arr[i - 1] as number) > 1) acc.push('...')
              acc.push(p)
              return acc
            }, [])
            .map((p, i) =>
              typeof p === 'string' ? (
                <span key={`dots-${i}`} className="px-2 text-gray-600">...</span>
              ) : (
                <Link
                  key={p}
                  href={filterUrl({ page: p })}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    p === activePage
                      ? 'bg-indigo-500 text-white'
                      : 'bg-white/5 hover:bg-white/10 text-gray-400'
                  }`}
                >
                  {p}
                </Link>
              )
            )}
          {activePage < totalPages && (
            <Link
              href={filterUrl({ page: activePage + 1 })}
              className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 text-sm transition-colors"
            >
              {locale === 'ko' ? '다음' : 'Next'} →
            </Link>
          )}
        </nav>
      )}

      {/* Info footer */}
      <div className="mt-12 pt-8 border-t border-white/5">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <h3 className="text-lg font-semibold text-white mb-2">
              {locale === 'ko' ? '급변동 종목이란?' : 'What are Rapid Change Alerts?'}
            </h3>
            <p className="text-sm text-gray-500 max-w-2xl">
              {locale === 'ko'
                ? 'FOR(포렌식) 보고서는 시장에서 급격한 변화가 감지된 프로젝트를 심층 분석합니다. 72시간 이내 생성된 보고서는 현재 진행 중인 중요한 시장 이벤트를 나타냅니다.'
                : 'FOR (Forensic) reports provide deep analysis of projects with detected rapid market changes. Reports created within 72 hours indicate ongoing critical market events.'}
            </p>
          </div>
          <div className="text-center px-6 py-4 rounded-xl bg-red-500/10 border border-red-500/20">
            <div className="text-3xl font-bold text-red-400 mb-1">{totalCount}</div>
            <div className="text-xs text-gray-500 uppercase">
              {locale === 'ko' ? '최근 72시간' : 'Last 72 Hours'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
