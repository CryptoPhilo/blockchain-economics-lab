import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import Link from 'next/link'
import type { ProjectReport } from '@/lib/types'
import { prepareRapidChangeReports } from './reports-page-utils'

interface Props {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ page?: string; q?: string }>
}

const PAGE_SIZE = 20

const LANG_NAMES: Record<string, string> = {
  en: 'English', ko: '한국어', ja: '日本語', zh: '中文',
  fr: 'Français', es: 'Español', de: 'Deutsch',
}

const FORENSIC_CONFIG = {
  color: 'bg-red-500/20 text-red-400 border-red-500/30',
  label: 'FOR',
  icon: '🔍'
} as const

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getLocalizedTitle(report: any, locale: string): string {
  const key = `title_${locale}`
  if (report[key]) return report[key]
  if (report.title_en) return report.title_en
  const project = report.project
  const typeName = locale === 'ko' ? '포렌식 분석' : 'Forensic Analysis'
  const name = project?.name || project?.symbol || ''
  return name ? `${name} ${typeName} v${report.version}` : `${typeName} v${report.version}`
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

export default async function ReportsPage({ params, searchParams }: Props) {
  const { locale } = await params
  const { page: pageStr, q: searchQuery } = await searchParams
  const supabase = await createServerSupabaseClient()
  const t = await getTranslations('reports')
  const currentPage = Math.max(1, parseInt(pageStr || '1', 10))

  const seventyTwoHoursAgo = new Date()
  seventyTwoHoursAgo.setHours(seventyTwoHoursAgo.getHours() - 72)

  const dataQuery = supabase
    .from('project_reports')
    .select('*, project:tracked_projects(id, name, slug, symbol, chain, category)')
    .in('status', ['published', 'coming_soon'])
    .eq('report_type', 'forensic')
    .gte('created_at', seventyTwoHoursAgo.toISOString())
    .order('published_at', { ascending: false })
    .order('created_at', { ascending: false })

  const { data: rawReports } = await dataQuery
  const { reports, totalCount, totalPages, currentPage: activePage } = prepareRapidChangeReports({
    reports: (rawReports || []) as ProjectReport[],
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
          {reports.map((report: ProjectReport) => {
            const project = report.project
            const config = FORENSIC_CONFIG
            const title = getLocalizedTitle(report, locale)

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

            const reportTime = report.published_at || report.created_at
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
                          className="hover:text-red-400 transition-colors font-medium"
                        >
                          {project.name} ({project.symbol})
                        </Link>
                      )}
                      {project?.category && (
                        <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-600">{project.category}</span>
                      )}
                      <span>v{report.version}</span>
                      {report.published_at && (
                        <span>{formatDate(report.published_at)}</span>
                      )}
                    </div>
                  </div>

                  {report.status === 'coming_soon' ? (
                    <span className="px-4 py-2 bg-amber-500/10 text-amber-400 text-sm font-medium rounded-lg border border-amber-500/20 cursor-default shrink-0">
                      🔜 Coming Soon
                    </span>
                  ) : project ? (
                    <Link
                      href={`/${locale}/reports/forensic/${project.slug}`}
                      className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 hover:text-red-300 text-sm font-medium rounded-lg transition-colors shrink-0 border border-red-500/30"
                    >
                      {locale === 'ko' ? '보고서 상세' : 'Report Details'} →
                    </Link>
                  ) : null}
                </div>

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
