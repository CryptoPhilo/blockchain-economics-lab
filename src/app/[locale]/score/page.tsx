import { getTranslations } from 'next-intl/server'
import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import MaturityScoreRadar from '@/components/MaturityScoreRadar'
import DisclaimerBanner from '@/components/DisclaimerBanner'
import type { Locale } from '@/lib/types'

interface Props {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ project?: string; q?: string; category?: string }>
}

const PAGE_SIZE = 24

export default async function ScoreLookupPage({ params, searchParams }: Props) {
  const { locale } = await params
  const { project: projectSlug, q: searchQuery, category: filterCategory } = await searchParams
  const isKo = locale === 'ko'

  const supabase = await createServerSupabaseClient()

  // Build query for the project list with DB-level search/filter
  let listQuery = supabase
    .from('tracked_projects')
    .select('id, name, slug, symbol, maturity_score, maturity_stage, chain, category')
    .in('status', ['active', 'monitoring_only'])
    .order('maturity_score', { ascending: false, nullsFirst: false })

  if (filterCategory && filterCategory !== 'all') {
    listQuery = listQuery.eq('category', filterCategory)
  }

  if (searchQuery && searchQuery.trim()) {
    const q = `%${searchQuery.trim()}%`
    listQuery = listQuery.or(`name.ilike.${q},symbol.ilike.${q}`)
  }

  const { data: projects } = await listQuery.limit(PAGE_SIZE)

  // Category counts for filter pills
  const { data: allProjects } = await supabase
    .from('tracked_projects')
    .select('category')
    .in('status', ['active', 'monitoring_only'])

  const catCountMap: Record<string, number> = {}
  allProjects?.forEach((c) => {
    const cat = c.category || 'Other'
    catCountMap[cat] = (catCountMap[cat] || 0) + 1
  })
  const totalProjects = allProjects?.length || 0
  const categories = Object.keys(catCountMap).sort()

  // Fetch selected project with full score data
  let selectedProject: any = null
  if (projectSlug) {
    const { data } = await supabase
      .from('tracked_projects')
      .select('id, name, slug, symbol, maturity_score, maturity_stage, score_technology, score_business, score_tokenomics, score_governance, score_community, score_compliance, score_narrative, threat_level, market_cap_usd, chain, category')
      .eq('slug', projectSlug)
      .single()
    selectedProject = data
  }

  // Build URL helper preserving search/filter state
  function buildUrl(p: { project?: string; q?: string; category?: string }) {
    const sp = new URLSearchParams()
    const proj = p.project !== undefined ? p.project : (projectSlug || '')
    const query = p.q !== undefined ? p.q : (searchQuery || '')
    const cat = p.category !== undefined ? p.category : (filterCategory || '')
    if (proj) sp.set('project', proj)
    if (query) sp.set('q', query)
    if (cat && cat !== 'all') sp.set('category', cat)
    const qs = sp.toString()
    return `/${locale}/score${qs ? `?${qs}` : ''}`
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm mb-6">
          <span>📊</span>
          BCE Maturity Score™
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">
          {isKo ? '프로젝트 성숙도 점수 조회' : 'Project Score Lookup'}
        </h1>
        <p className="text-gray-400 max-w-2xl mx-auto">
          {isKo
            ? '7축 가중 평가 체계로 블록체인 프로젝트의 성숙도를 종합 평가합니다.'
            : 'Comprehensive 7-axis weighted assessment of blockchain project maturity.'}
        </p>
      </div>

      {/* Search + Category Filters */}
      <div className="space-y-4 mb-8">
        <form action={`/${locale}/score`} method="GET" className="flex gap-3">
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">🔍</span>
            <input
              type="text"
              name="q"
              defaultValue={searchQuery || ''}
              placeholder={isKo ? '프로젝트명 또는 심볼 검색...' : 'Search by name or symbol...'}
              className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/30"
            />
          </div>
          {filterCategory && filterCategory !== 'all' && <input type="hidden" name="category" value={filterCategory} />}
          {projectSlug && <input type="hidden" name="project" value={projectSlug} />}
          <button
            type="submit"
            className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl transition-colors"
          >
            {isKo ? '검색' : 'Search'}
          </button>
        </form>

        {/* Category pills */}
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={buildUrl({ category: 'all', q: searchQuery || '' })}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              !filterCategory || filterCategory === 'all'
                ? 'bg-indigo-500 text-white'
                : 'bg-white/5 text-gray-400 hover:bg-white/10'
            }`}
          >
            {isKo ? '전체' : 'All'} ({totalProjects})
          </Link>
          {categories.map((cat) => (
            <Link
              key={cat}
              href={buildUrl({ category: cat, q: searchQuery || '' })}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                filterCategory === cat
                  ? 'bg-indigo-500/20 text-indigo-400 ring-1 ring-indigo-500/30'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'
              }`}
            >
              {cat} ({catCountMap[cat]})
            </Link>
          ))}
        </div>
      </div>

      {/* Project Selection — compact list instead of large grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-12">
        {projects?.map((p) => (
          <Link
            key={p.id}
            href={buildUrl({ project: p.slug })}
            className={`p-4 rounded-xl border transition-all ${
              selectedProject?.id === p.id
                ? 'bg-indigo-500/10 border-indigo-500/30'
                : 'bg-white/5 border-white/5 hover:border-indigo-500/20 hover:bg-white/10'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <h3 className="font-semibold text-white truncate">{p.name}</h3>
                <p className="text-xs text-gray-500 mt-1 truncate">
                  {p.symbol} · {p.chain || '—'} · {p.category || '—'}
                </p>
              </div>
              <div className={`text-2xl font-bold shrink-0 ml-3 ${
                (p.maturity_score || 0) >= 80 ? 'text-green-400' :
                (p.maturity_score || 0) >= 60 ? 'text-yellow-400' :
                (p.maturity_score || 0) >= 40 ? 'text-orange-400' : 'text-red-400'
              }`}>
                {p.maturity_score?.toFixed(1) || '—'}
              </div>
            </div>
          </Link>
        ))}

        {(!projects || projects.length === 0) && (
          <div className="col-span-3 text-center py-12 text-gray-500">
            {searchQuery
              ? (isKo ? `"${searchQuery}" 검색 결과가 없습니다` : `No results for "${searchQuery}"`)
              : (isKo ? '추적 중인 프로젝트가 없습니다.' : 'No tracked projects available.')}
          </div>
        )}
      </div>

      {/* Selected Project Score Detail */}
      {selectedProject && (
        <div className="space-y-6">
          <MaturityScoreRadar
            scores={{
              technology: selectedProject.score_technology || 0,
              business: selectedProject.score_business || 0,
              tokenomics: selectedProject.score_tokenomics || 0,
              governance: selectedProject.score_governance || 0,
              community: selectedProject.score_community || 0,
              compliance: selectedProject.score_compliance || 0,
              narrative: selectedProject.score_narrative || 0,
            }}
            overallScore={selectedProject.maturity_score || 0}
            projectName={selectedProject.name}
            threatLevel={selectedProject.threat_level as any || 'clear'}
          />

          {/* CTAs */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Link
              href={`/${locale}/projects/${selectedProject.slug}`}
              className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-center hover:bg-blue-500/20 transition-colors"
            >
              <span className="text-2xl block mb-2">📊</span>
              <span className="text-sm font-medium text-blue-400">
                {isKo ? '전체 보고서 보기' : 'View Full Reports'}
              </span>
            </Link>
            <Link
              href={`/${locale}/subscribe`}
              className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-center hover:bg-indigo-500/20 transition-colors"
            >
              <span className="text-2xl block mb-2">📧</span>
              <span className="text-sm font-medium text-indigo-400">
                {isKo ? '무료 뉴스레터 구독' : 'Free Newsletter'}
              </span>
            </Link>
            <Link
              href={`/${locale}/products?type=subscription`}
              className="p-4 rounded-xl bg-green-500/10 border border-green-500/20 text-center hover:bg-green-500/20 transition-colors"
            >
              <span className="text-2xl block mb-2">🔄</span>
              <span className="text-sm font-medium text-green-400">
                360° {isKo ? '구독하기' : 'Subscribe'}
              </span>
            </Link>
          </div>
        </div>
      )}

      {/* Methodology Section */}
      <div className="mt-16 rounded-2xl bg-white/5 border border-white/10 p-8">
        <h2 className="text-xl font-bold text-white mb-4">
          {isKo ? '평가 방법론' : 'Scoring Methodology'}
        </h2>
        <p className="text-sm text-gray-400 mb-6">
          {isKo
            ? 'BCE Maturity Score™는 7개 축의 가중 평균으로 산출됩니다. 각 축은 0-100점으로 평가되며, 전체 점수는 아래 가중치를 반영합니다.'
            : 'BCE Maturity Score™ is calculated as a weighted average of 7 axes. Each axis is scored 0-100, and the overall score reflects the weights below.'}
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Technology', weight: '20%', icon: '⚙️' },
            { label: 'Business Model', weight: '20%', icon: '💼' },
            { label: 'Tokenomics', weight: '15%', icon: '🪙' },
            { label: 'Governance', weight: '10%', icon: '🏛️' },
            { label: 'Community', weight: '10%', icon: '👥' },
            { label: 'Compliance', weight: '10%', icon: '📋' },
            { label: 'Narrative Health', weight: '15%', icon: '📈' },
          ].map((axis) => (
            <div key={axis.label} className="p-3 rounded-lg bg-white/5 text-center">
              <span className="text-lg">{axis.icon}</span>
              <p className="text-xs font-medium text-gray-300 mt-1">{axis.label}</p>
              <p className="text-xs text-indigo-400 mt-0.5">{axis.weight}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-8">
        <DisclaimerBanner />
      </div>
    </div>
  )
}
