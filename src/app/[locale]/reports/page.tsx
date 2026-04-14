import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import Link from 'next/link'

interface Props {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ type?: string; project?: string; page?: string; q?: string }>
}

const PAGE_SIZE = 20

const LANG_NAMES: Record<string, string> = {
  en: 'English', ko: '한국어', ja: '日本語', zh: '中文',
  fr: 'Français', es: 'Español', de: 'Deutsch',
}

 
const TYPE_CONFIG = {
  econ: { color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', label: 'ECON', icon: '📊' },
  maturity: { color: 'bg-green-500/20 text-green-400 border-green-500/30', label: 'MAT', icon: '📈' },
  forensic: { color: 'bg-red-500/20 text-red-400 border-red-500/30', label: 'FOR', icon: '🔍' },
} as const

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getLocalizedTitle(report: any, locale: string): string {
  const key = `title_${locale}`
  if (report[key]) return report[key]
  if (report.title_en) return report.title_en
  // Fallback: use project name + report type instead of generic "Report v1"
  const project = report.project
  const typeName = report.report_type === 'forensic' ? (locale === 'ko' ? '포렌식 분석' : 'Forensic Analysis')
    : report.report_type === 'econ' ? (locale === 'ko' ? '경제 분석' : 'Economic Analysis')
    : (locale === 'ko' ? '성숙도 분석' : 'Maturity Analysis')
  const name = project?.name || project?.symbol || ''
  return name ? `${name} ${typeName} v${report.version}` : `${typeName} v${report.version}`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export default async function ReportsPage({ params, searchParams }: Props) {
  const { locale } = await params
  const { type: filterType, project: filterProject, page: pageStr, q: searchQuery } = await searchParams
  const supabase = await createServerSupabaseClient()
  const t = await getTranslations('reports')
  const currentPage = Math.max(1, parseInt(pageStr || '1', 10))

  // Fetch all projects for the dropdown (lightweight query)
  const { data: allProjects } = await supabase
    .from('tracked_projects')
    .select('id, name, slug, symbol, category')
    .in('status', ['active', 'monitoring_only'])
    .order('name')

  // Resolve project filter to project_id for DB-level filtering
  let filterProjectId: string | null = null
  if (filterProject && filterProject !== 'all' && allProjects) {
    const found = allProjects.find((p) => p.slug === filterProject)
    if (found) filterProjectId = found.id
  }

  // Build optimized Supabase query with DB-level filters
  // Include both 'published' and 'coming_soon' reports (OPS-007)
  let countQuery = supabase
    .from('project_reports')
    .select('id', { count: 'exact', head: true })
    .in('status', ['published', 'coming_soon'])

  let dataQuery = supabase
    .from('project_reports')
    .select('*, project:tracked_projects(id, name, slug, symbol, chain, category)')
    .in('status', ['published', 'coming_soon'])
    .order('published_at', { ascending: false, nullsFirst: false })

  // Apply type filter at DB level
  if (filterType && filterType !== 'all') {
    countQuery = countQuery.eq('report_type', filterType)
    dataQuery = dataQuery.eq('report_type', filterType)
  }

  // Apply project filter at DB level
  if (filterProjectId) {
    countQuery = countQuery.eq('project_id', filterProjectId)
    dataQuery = dataQuery.eq('project_id', filterProjectId)
  }

  // Apply search filter (title search)
  if (searchQuery && searchQuery.trim()) {
    const q = `%${searchQuery.trim()}%`
    countQuery = countQuery.ilike('title_en', q)
    dataQuery = dataQuery.ilike('title_en', q)
  }

  // Pagination
  const from = (currentPage - 1) * PAGE_SIZE
  const to = from + PAGE_SIZE - 1
  dataQuery = dataQuery.range(from, to)

  // Execute both queries in parallel
  const [{ count: totalCount }, { data: reports }] = await Promise.all([
    countQuery,
    dataQuery,
  ])

  const totalPages = Math.ceil((totalCount || 0) / PAGE_SIZE)

  // Get type counts for filter badges (separate lightweight query)
  const { data: typeCounts } = await supabase
    .from('project_reports')
    .select('report_type')
    .eq('status', 'published')

  const typeCountMap: Record<string, number> = {}
  typeCounts?.forEach((r) => {
    typeCountMap[r.report_type] = (typeCountMap[r.report_type] || 0) + 1
  })
  const totalReports = typeCounts?.length || 0

  // Build filter URL helper
  function filterUrl(params: { type?: string; project?: string; page?: number; q?: string }) {
    const sp = new URLSearchParams()
    const t = params.type !== undefined ? params.type : (filterType || 'all')
    const p = params.project !== undefined ? params.project : (filterProject || 'all')
    const pg = params.page !== undefined ? params.page : (params.type !== undefined || params.project !== undefined || params.q !== undefined ? 1 : currentPage)
    const query = params.q !== undefined ? params.q : (searchQuery || '')
    if (t && t !== 'all') sp.set('type', t)
    if (p && p !== 'all') sp.set('project', p)
    if (pg > 1) sp.set('page', String(pg))
    if (query) sp.set('q', query)
    const qs = sp.toString()
    return `/${locale}/reports${qs ? `?${qs}` : ''}`
  }

  const projects = allProjects || []

  // Group projects by category for the dropdown
  const categoryGroups = new Map<string, typeof projects>()
  projects.forEach((p) => {
    const cat = p.category || 'Other'
    if (!categoryGroups.has(cat)) categoryGroups.set(cat, [])
    categoryGroups.get(cat)!.push(p)
  })

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-4xl font-bold mb-2">{t('title')}</h1>
        <p className="text-gray-400">{t('subtitle')}</p>
      </div>

      {/* Search + Filters Bar */}
      <div className="space-y-4 mb-8">
        {/* Search */}
        <form action={`/${locale}/reports`} method="GET" className="flex gap-3">
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">🔍</span>
            <input
              type="text"
              name="q"
              defaultValue={searchQuery || ''}
              placeholder={locale === 'ko' ? '프로젝트명, 심볼로 검색...' : 'Search by project name or symbol...'}
              className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/30"
            />
          </div>
          {filterType && filterType !== 'all' && <input type="hidden" name="type" value={filterType} />}
          {filterProject && filterProject !== 'all' && <input type="hidden" name="project" value={filterProject} />}
          <button
            type="submit"
            className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl transition-colors"
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

        {/* Type filters + Project dropdown */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Type filter pills */}
          <Link
            href={filterUrl({ type: 'all' })}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              !filterType || filterType === 'all'
                ? 'bg-indigo-500 text-white'
                : 'bg-white/5 text-gray-400 hover:bg-white/10'
            }`}
          >
            {t('allTypes')} ({totalReports})
          </Link>
          {(Object.keys(TYPE_CONFIG) as Array<keyof typeof TYPE_CONFIG>).map((type) => {
            const config = TYPE_CONFIG[type]
            const count = typeCountMap[type] || 0
            if (count === 0) return null
            return (
              <Link
                key={type}
                href={filterUrl({ type })}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  filterType === type ? config.color + ' ring-1 ring-current' : 'bg-white/5 text-gray-400 hover:bg-white/10'
                }`}
              >
                {config.icon} {config.label} ({count})
              </Link>
            )
          })}

          <span className="w-px h-6 bg-white/10 mx-1" />

          {/* Project dropdown (replaces 50+ pill buttons) */}
          <div className="relative">
            <select
              defaultValue={filterProject || 'all'}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              onChange={`window.location.href='${filterUrl({ project: '__PROJ__' })}'.replace('__PROJ__', this.value)` as any}
              className="appearance-none pl-4 pr-10 py-2 rounded-full text-sm font-medium bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10 cursor-pointer focus:outline-none focus:border-indigo-500/50"
            >
              <option value="all">{t('allProjects')} ({projects.length})</option>
              {Array.from(categoryGroups.entries()).map(([cat, projs]) => (
                <optgroup key={cat} label={`── ${cat} ──`}>
                  {projs.map((p) => (
                    <option key={p.slug} value={p.slug}>
                      {p.symbol} — {p.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">▾</span>
          </div>
        </div>

        {/* Active filters summary */}
        {(searchQuery || (filterProject && filterProject !== 'all') || (filterType && filterType !== 'all')) && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>{locale === 'ko' ? '필터:' : 'Filters:'}</span>
            {filterType && filterType !== 'all' && (
              <span className="px-2 py-0.5 rounded bg-white/5 text-gray-400">
                {TYPE_CONFIG[filterType as keyof typeof TYPE_CONFIG]?.label || filterType}
              </span>
            )}
            {filterProject && filterProject !== 'all' && (
              <span className="px-2 py-0.5 rounded bg-white/5 text-gray-400">
                {projects.find((p) => p.slug === filterProject)?.symbol || filterProject}
              </span>
            )}
            {searchQuery && (
              <span className="px-2 py-0.5 rounded bg-white/5 text-gray-400">
                &quot;{searchQuery}&quot;
              </span>
            )}
            <Link href={`/${locale}/reports`} className="text-indigo-400 hover:text-indigo-300 ml-2">
              {locale === 'ko' ? '초기화' : 'Clear all'}
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
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {reports.map((report: any) => {
            const project = report.project
            const typeKey = report.report_type as keyof typeof TYPE_CONFIG
            const config = TYPE_CONFIG[typeKey] || TYPE_CONFIG.econ
            const title = getLocalizedTitle(report, locale)

            const translationStatus = report.translation_status || {}
            const gdriveUrls = report.gdrive_urls_by_lang || {}
            const availableLangs = [...new Set([
              ...Object.keys(gdriveUrls),
              ...Object.entries(translationStatus)
                .filter(([, v]) => v === 'published')
                .map(([k]) => k)
            ])].sort()

            return (
              <div
                key={report.id}
                className="flex flex-col gap-4 p-6 rounded-2xl bg-white/[0.03] border border-white/5 hover:border-white/10 transition-colors"
              >
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                  <div className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase shrink-0 ${config.color}`}>
                    {config.icon} {config.label}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                      {project && (
                        <Link
                          href={`/${locale}/projects/${project.slug}`}
                          className="hover:text-indigo-400 transition-colors"
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

                  {/* Download button or Coming Soon badge (OPS-007) */}
                  {report.status === 'coming_soon' ? (
                    <span className="px-4 py-2 bg-amber-500/10 text-amber-400 text-sm font-medium rounded-lg border border-amber-500/20 cursor-default shrink-0">
                      🔜 Coming Soon
                    </span>
                  ) : gdriveUrls[locale] || gdriveUrls['en'] ? (
                    <a
                      href={gdriveUrls[locale] || gdriveUrls['en']}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 text-sm font-medium rounded-lg transition-colors shrink-0 border border-indigo-500/20"
                    >
                      📥 {t('downloadPdf')}
                    </a>
                  ) : project ? (
                    <Link
                      href={`/${locale}/projects/${project.slug}`}
                      className="px-4 py-2 bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white text-sm font-medium rounded-lg transition-colors shrink-0"
                    >
                      {t('viewProject')} →
                    </Link>
                  ) : null}
                </div>

                {/* Language badges */}
                {availableLangs.length > 1 && (
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/5">
                    <span className="text-xs text-gray-600 mr-1">{t('languages')}:</span>
                    {availableLangs.map((lang) => {
                      const url = gdriveUrls[lang]
                      const badge = (
                        <span
                          key={lang}
                          className={`px-2 py-0.5 rounded text-[11px] font-medium uppercase ${
                            lang === locale
                              ? 'bg-indigo-500/20 text-indigo-400 ring-1 ring-indigo-500/30'
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
        <div className="text-center py-20">
          <p className="text-gray-500 text-lg">{t('noReportsFound')}</p>
          {searchQuery && (
            <Link href={`/${locale}/reports`} className="text-indigo-400 hover:text-indigo-300 mt-4 inline-block">
              {locale === 'ko' ? '필터 초기화' : 'Clear filters'} →
            </Link>
          )}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <nav className="flex items-center justify-center gap-2 mt-10">
          {currentPage > 1 && (
            <Link
              href={filterUrl({ page: currentPage - 1 })}
              className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 text-sm transition-colors"
            >
              ← {locale === 'ko' ? '이전' : 'Prev'}
            </Link>
          )}
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 2)
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
                    p === currentPage
                      ? 'bg-indigo-500 text-white'
                      : 'bg-white/5 hover:bg-white/10 text-gray-400'
                  }`}
                >
                  {p}
                </Link>
              )
            )}
          {currentPage < totalPages && (
            <Link
              href={filterUrl({ page: currentPage + 1 })}
              className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 text-sm transition-colors"
            >
              {locale === 'ko' ? '다음' : 'Next'} →
            </Link>
          )}
        </nav>
      )}

      {/* Stats footer */}
      <div className="mt-12 pt-8 border-t border-white/5 flex flex-wrap items-center justify-center gap-8 text-sm text-gray-600">
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{totalReports}</div>
          <div>{t('title')}</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{projects.length}</div>
          <div>{t('allProjects')}</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white">7</div>
          <div>{t('languages')}</div>
        </div>
      </div>
    </div>
  )
}
