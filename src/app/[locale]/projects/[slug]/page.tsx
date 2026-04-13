import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { type Locale, getLocalizedField, formatPrice } from '@/lib/types'
import Link from 'next/link'
import { notFound } from 'next/navigation'

interface Props {
  params: Promise<{ locale: string; slug: string }>
  searchParams: Promise<{ tab?: string }>
}

function formatMarketCap(value?: number | null): string {
  if (!value) return '—'
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`
  return `$${value.toLocaleString()}`
}

const REPORT_TYPES = ['econ', 'maturity', 'forensic'] as const
const TYPE_CONFIG = {
  econ:      { color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',  activeColor: 'bg-blue-500 text-white', icon: '📊' },
  maturity:  { color: 'bg-green-500/20 text-green-400 border-green-500/30', activeColor: 'bg-green-500 text-white', icon: '📈' },
  forensic:  { color: 'bg-red-500/20 text-red-400 border-red-500/30',    activeColor: 'bg-red-500 text-white', icon: '🔍' },
}

export default async function ProjectDetailPage({ params, searchParams }: Props) {
  const { locale, slug } = await params
  const { tab } = await searchParams
  const activeTab = tab || 'all'
  const supabase = await createServerSupabaseClient()
  const t = await getTranslations('projects')

  // Fetch project
  const { data: project } = await supabase
    .from('tracked_projects')
    .select('*')
    .eq('slug', slug)
    .single()

  if (!project) notFound()

  // Fetch reports with linked products
  let reportsQuery = supabase
    .from('project_reports')
    .select('*, product:products(*)')
    .eq('project_id', project.id)
    .eq('status', 'published')
    .order('report_type')
    .order('version', { ascending: false })

  if (activeTab !== 'all') {
    reportsQuery = reportsQuery.eq('report_type', activeTab)
  }

  const { data: reports } = await reportsQuery

  // Count reports by type for tab badges
  const { data: allReports } = await supabase
    .from('project_reports')
    .select('report_type')
    .eq('project_id', project.id)
    .eq('status', 'published')

  const counts: Record<string, number> = { econ: 0, maturity: 0, forensic: 0 }
  allReports?.forEach(r => counts[r.report_type]++)

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-8">
        <Link href={`/${locale}/projects`} className="hover:text-indigo-400 transition-colors">
          {t('allProjects')}
        </Link>
        <span>/</span>
        <span className="text-gray-300">{project.name}</span>
      </div>

      {/* Project Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-10">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold">{project.name}</h1>
            <span className="px-3 py-1 rounded-lg bg-white/10 text-sm font-mono text-gray-300">
              {project.symbol}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500">
            {project.chain && (
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                {t('chain')}: {project.chain}
              </span>
            )}
            {project.category && (
              <span>{t('category')}: {project.category}</span>
            )}
            <span>{t('marketCap')}: {formatMarketCap(project.market_cap_usd)}</span>
            {project.forensic_monitoring && (
              <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-400 text-xs">
                {t('forensicMonitoring')}: {t('active')}
              </span>
            )}
          </div>
        </div>

        {/* Maturity score badge */}
        {project.maturity_score && (
          <div className="flex flex-col items-center px-6 py-3 rounded-xl bg-white/[0.03] border border-white/10">
            <span className={`text-3xl font-bold ${
              Number(project.maturity_score) >= 70 ? 'text-green-400' :
              Number(project.maturity_score) >= 40 ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {Number(project.maturity_score).toFixed(0)}
            </span>
            <span className="text-xs text-gray-500 mt-1">{t('maturityScore')}</span>
            {project.maturity_stage && (
              <span className="text-xs text-gray-600 capitalize">{project.maturity_stage}</span>
            )}
          </div>
        )}
      </div>

      {/* Report Type Tabs */}
      <div className="flex items-center gap-2 mb-8 overflow-x-auto pb-2">
        <Link
          href={`/${locale}/projects/${slug}`}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors whitespace-nowrap ${
            activeTab === 'all'
              ? 'bg-indigo-500 text-white'
              : 'bg-white/5 text-gray-400 hover:bg-white/10'
          }`}
        >
          All ({(allReports?.length || 0)})
        </Link>
        {REPORT_TYPES.map((type) => {
          const config = TYPE_CONFIG[type]
          const count = counts[type]
          const isActive = activeTab === type
          const labelKey = type === 'econ' ? 'econReport' : type === 'maturity' ? 'maturityReport' : 'forensicReport'

          return (
            <Link
              key={type}
              href={`/${locale}/projects/${slug}?tab=${type}`}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors whitespace-nowrap ${
                isActive ? config.activeColor : config.color
              }`}
            >
              {config.icon} {t(labelKey)} ({count})
            </Link>
          )
        })}
      </div>

      {/* Reports Grid */}
      {reports && reports.length > 0 ? (
        <div className="grid gap-4">
          {reports.map((report: any) => {
            const typeKey = report.report_type as keyof typeof TYPE_CONFIG
            const config = TYPE_CONFIG[typeKey]
            const product = report.product
            const title = product
              ? getLocalizedField(product, 'title', locale as Locale)
              : `${project.name} ${report.report_type.toUpperCase()} v${report.version}`
            const description = product
              ? getLocalizedField(product, 'description', locale as Locale)
              : ''

            // Translation status
            const ts = report.translation_status || {}
            const completedLangs = Object.entries(ts).filter(([, v]) => v === 'completed').map(([k]) => k)
            const gdriveLangs = report.gdrive_urls_by_lang ? Object.keys(report.gdrive_urls_by_lang) : []
            const availableLangs = [...new Set([...completedLangs, ...gdriveLangs])]

            return (
              <div
                key={report.id}
                className="flex flex-col sm:flex-row items-start sm:items-center gap-4 p-6 rounded-2xl bg-white/[0.03] border border-white/5"
              >
                {/* Report type badge */}
                <div className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase ${config.color}`}>
                  {config.icon} {report.report_type}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-semibold text-white mb-1 truncate">{title}</h3>
                  {description && (
                    <p className="text-sm text-gray-500 line-clamp-2 mb-2">{description}</p>
                  )}
                  <div className="flex items-center gap-3 text-xs text-gray-600">
                    <span>v{report.version}</span>
                    {report.page_count && <span>{report.page_count} pages</span>}
                    {availableLangs.length > 0 && (
                      <span className="flex items-center gap-1">
                        {t('language')}:
                        {availableLangs.map(lang => (
                          <span key={lang} className="px-1.5 py-0.5 bg-green-500/10 text-green-400 rounded text-[10px] uppercase">
                            {lang}
                          </span>
                        ))}
                      </span>
                    )}
                  </div>
                </div>

                {/* Price + CTA */}
                <div className="flex items-center gap-3">
                  {product && (
                    <span className="text-xl font-bold text-indigo-400">
                      {formatPrice(product.price_usd_cents)}
                    </span>
                  )}
                  {product ? (
                    <Link
                      href={`/${locale}/products/${product.slug}`}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      {t('buyReport')}
                    </Link>
                  ) : report.gdrive_url ? (
                    <a
                      href={report.gdrive_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      {t('viewReport')}
                    </a>
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-center py-20 text-gray-500">{t('noReports')}</div>
      )}
    </div>
  )
}
