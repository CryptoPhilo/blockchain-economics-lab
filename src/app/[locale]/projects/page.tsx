import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import Link from 'next/link'

interface Props {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ category?: string; page?: string; q?: string }>
}

const PAGE_SIZE = 20

function formatMarketCap(value?: number | null): string {
  if (!value) return '—'
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`
  return `$${value.toLocaleString()}`
}

function maturityColor(score?: number | null): string {
  if (!score) return 'text-gray-500'
  if (score >= 70) return 'text-green-400'
  if (score >= 40) return 'text-yellow-400'
  return 'text-red-400'
}

export default async function ProjectsPage({ params, searchParams }: Props) {
  const { locale } = await params
  const { category: filterCategory, page: pageStr, q: searchQuery } = await searchParams
  const supabase = await createServerSupabaseClient()
  const t = await getTranslations('projects')
  const currentPage = Math.max(1, parseInt(pageStr || '1', 10))

  // Get distinct categories for the filter dropdown
  const { data: allCategories } = await supabase
    .from('tracked_projects')
    .select('category')
    .in('status', ['active', 'monitoring_only'])
    .not('category', 'is', null)

  const categories = [...new Set((allCategories || []).map((c) => c.category).filter(Boolean))].sort()

  // Build count query
  let countQuery = supabase
    .from('tracked_projects')
    .select('id', { count: 'exact', head: true })
    .in('status', ['active', 'monitoring_only'])

  // Build data query
  let dataQuery = supabase
    .from('tracked_projects')
    .select('*')
    .in('status', ['active', 'monitoring_only'])
    .order('market_cap_usd', { ascending: false, nullsFirst: false })

  // Apply category filter at DB level
  if (filterCategory && filterCategory !== 'all') {
    countQuery = countQuery.eq('category', filterCategory)
    dataQuery = dataQuery.eq('category', filterCategory)
  }

  // Apply search filter (name or symbol)
  if (searchQuery && searchQuery.trim()) {
    const q = `%${searchQuery.trim()}%`
    // Search by name OR symbol using Supabase or filter
    countQuery = countQuery.or(`name.ilike.${q},symbol.ilike.${q}`)
    dataQuery = dataQuery.or(`name.ilike.${q},symbol.ilike.${q}`)
  }

  // Pagination range
  const from = (currentPage - 1) * PAGE_SIZE
  const to = from + PAGE_SIZE - 1
  dataQuery = dataQuery.range(from, to)

  // Execute count + data in parallel
  const [{ count: totalCount }, { data: projects }] = await Promise.all([
    countQuery,
    dataQuery,
  ])

  const totalPages = Math.ceil((totalCount || 0) / PAGE_SIZE)

  // Get report counts per project (only for displayed projects)
  const projectIds = (projects || []).map((p) => p.id)
  const reportMap: Record<string, { econ: number; maturity: number; forensic: number }> = {}

  if (projectIds.length > 0) {
    const { data: reports } = await supabase
      .from('project_reports')
      .select('project_id, report_type')
      .eq('status', 'published')
      .in('project_id', projectIds)

    reports?.forEach((r) => {
      if (!reportMap[r.project_id]) reportMap[r.project_id] = { econ: 0, maturity: 0, forensic: 0 }
      reportMap[r.project_id][r.report_type as 'econ' | 'maturity' | 'forensic']++
    })
  }

  // Category counts for filter badges
  const { data: catCounts } = await supabase
    .from('tracked_projects')
    .select('category')
    .in('status', ['active', 'monitoring_only'])

  const catCountMap: Record<string, number> = {}
  catCounts?.forEach((c) => {
    const cat = c.category || 'Other'
    catCountMap[cat] = (catCountMap[cat] || 0) + 1
  })
  const totalProjects = catCounts?.length || 0

  // Build filter URL helper
  function filterUrl(p: { category?: string; page?: number; q?: string }) {
    const sp = new URLSearchParams()
    const cat = p.category !== undefined ? p.category : (filterCategory || 'all')
    const pg = p.page !== undefined ? p.page : (p.category !== undefined || p.q !== undefined ? 1 : currentPage)
    const query = p.q !== undefined ? p.q : (searchQuery || '')
    if (cat && cat !== 'all') sp.set('category', cat)
    if (pg > 1) sp.set('page', String(pg))
    if (query) sp.set('q', query)
    const qs = sp.toString()
    return `/${locale}/projects${qs ? `?${qs}` : ''}`
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-4xl font-bold mb-2">{t('title')}</h1>
        <p className="text-gray-400 mb-2">{t('subtitle')}</p>
      </div>

      {/* Search + Filters */}
      <div className="space-y-4 mb-8">
        {/* Search bar */}
        <form action={`/${locale}/projects`} method="GET" className="flex gap-3">
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">🔍</span>
            <input
              type="text"
              name="q"
              defaultValue={searchQuery || ''}
              placeholder={locale === 'ko' ? '프로젝트명, 심볼로 검색...' : 'Search by name or symbol...'}
              className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/30"
            />
          </div>
          {filterCategory && filterCategory !== 'all' && <input type="hidden" name="category" value={filterCategory} />}
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

        {/* Category filter pills */}
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={filterUrl({ category: 'all' })}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              !filterCategory || filterCategory === 'all'
                ? 'bg-indigo-500 text-white'
                : 'bg-white/5 text-gray-400 hover:bg-white/10'
            }`}
          >
            {locale === 'ko' ? '전체' : 'All'} ({totalProjects})
          </Link>
          {categories.map((cat) => {
            const count = catCountMap[cat] || 0
            if (count === 0) return null
            return (
              <Link
                key={cat}
                href={filterUrl({ category: cat })}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  filterCategory === cat
                    ? 'bg-indigo-500/20 text-indigo-400 ring-1 ring-indigo-500/30'
                    : 'bg-white/5 text-gray-400 hover:bg-white/10'
                }`}
              >
                {cat} ({count})
              </Link>
            )
          })}
        </div>

        {/* Active filters summary */}
        {(searchQuery || (filterCategory && filterCategory !== 'all')) && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>{locale === 'ko' ? '필터:' : 'Filters:'}</span>
            {filterCategory && filterCategory !== 'all' && (
              <span className="px-2 py-0.5 rounded bg-white/5 text-gray-400">{filterCategory}</span>
            )}
            {searchQuery && (
              <span className="px-2 py-0.5 rounded bg-white/5 text-gray-400">&quot;{searchQuery}&quot;</span>
            )}
            <Link href={`/${locale}/projects`} className="text-indigo-400 hover:text-indigo-300 ml-2">
              {locale === 'ko' ? '초기화' : 'Clear all'}
            </Link>
            <span className="ml-auto text-gray-600">
              {totalCount || 0} {locale === 'ko' ? '건' : 'results'}
            </span>
          </div>
        )}
      </div>

      {/* Projects List */}
      {projects && projects.length > 0 ? (
        <div className="grid gap-4">
          {projects.map((project) => {
            const counts = reportMap[project.id] || { econ: 0, maturity: 0, forensic: 0 }
            const totalReports = counts.econ + counts.maturity + counts.forensic

            return (
              <Link
                key={project.id}
                href={`/${locale}/projects/${project.slug}`}
                className="group flex flex-col sm:flex-row items-start sm:items-center gap-4 p-6 rounded-2xl bg-white/[0.03] border border-white/5 hover:border-indigo-500/30 hover:bg-indigo-500/[0.03] transition-all duration-300"
              >
                {/* Project identity */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <h2 className="text-lg font-semibold text-white group-hover:text-indigo-400 transition-colors truncate">
                      {project.name}
                    </h2>
                    <span className="px-2 py-0.5 rounded bg-white/10 text-xs font-mono text-gray-400">
                      {project.symbol}
                    </span>
                    {project.chain && (
                      <span className="px-2 py-0.5 rounded bg-white/5 text-xs text-gray-500">
                        {project.chain}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    {project.category && <span>{project.category}</span>}
                    <span>{formatMarketCap(project.market_cap_usd)}</span>
                    {project.forensic_monitoring && (
                      <span className="text-red-400/70 text-xs">
                        {t('forensicMonitoring')}: {t('active')}
                      </span>
                    )}
                  </div>
                </div>

                {/* Maturity score */}
                {project.maturity_score && (
                  <div className="text-center px-4">
                    <div className={`text-2xl font-bold ${maturityColor(Number(project.maturity_score))}`}>
                      {Number(project.maturity_score).toFixed(0)}
                    </div>
                    <div className="text-xs text-gray-600">{t('maturityScore')}</div>
                  </div>
                )}

                {/* Report badges */}
                <div className="flex items-center gap-2">
                  <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${counts.econ > 0 ? 'bg-blue-500/20 text-blue-400' : 'bg-white/5 text-gray-600'}`}>
                    ECON {counts.econ > 0 ? `(${counts.econ})` : ''}
                  </span>
                  <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${counts.maturity > 0 ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-gray-600'}`}>
                    MAT {counts.maturity > 0 ? `(${counts.maturity})` : ''}
                  </span>
                  <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${counts.forensic > 0 ? 'bg-red-500/20 text-red-400' : 'bg-white/5 text-gray-600'}`}>
                    FOR {counts.forensic > 0 ? `(${counts.forensic})` : ''}
                  </span>
                  <span className="text-sm text-gray-500 ml-2">
                    {totalReports} {t('reports')}
                  </span>
                </div>

                {/* Arrow */}
                <span className="text-indigo-400 group-hover:translate-x-1 transition-transform hidden sm:block">
                  →
                </span>
              </Link>
            )
          })}
        </div>
      ) : (
        <div className="text-center py-20">
          <p className="text-gray-500 text-lg">
            {locale === 'ko' ? '프로젝트를 찾을 수 없습니다' : 'No projects found'}
          </p>
          {searchQuery && (
            <Link href={`/${locale}/projects`} className="text-indigo-400 hover:text-indigo-300 mt-4 inline-block">
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
          <div className="text-2xl font-bold text-white">{totalProjects}</div>
          <div>{locale === 'ko' ? '추적 프로젝트' : 'Tracked Projects'}</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{categories.length}</div>
          <div>{locale === 'ko' ? '카테고리' : 'Categories'}</div>
        </div>
      </div>
    </div>
  )
}
