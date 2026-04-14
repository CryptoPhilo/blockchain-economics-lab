import { createServerSupabaseClient } from '@/lib/supabase-server'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getTranslations } from 'next-intl/server'

interface Props {
  params: Promise<{ locale: string; slug: string }>
}

const riskConfig: Record<string, { color: string; bg: string; border: string; stroke: string }> = {
  critical: { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', stroke: '#EF4444' },
  high: { color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', stroke: '#F97316' },
  elevated: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', stroke: '#EAB308' },
}

// Locale → Intl locale string for date formatting
const localeMap: Record<string, string> = {
  en: 'en-US', ko: 'ko-KR', ja: 'ja-JP', zh: 'zh-CN',
  fr: 'fr-FR', es: 'es-ES', de: 'de-DE',
}

export default async function ForensicReportPage({ params }: Props) {
  const { locale, slug } = await params
  const t = await getTranslations('forensicDetail')
  const supabase = await createServerSupabaseClient()

  // Fetch the project
  const { data: project } = await supabase
    .from('tracked_projects')
    .select('*')
    .eq('slug', slug)
    .single()

  if (!project) notFound()

  // Fetch the latest forensic report for this project
  const { data: report } = await supabase
    .from('project_reports')
    .select('*')
    .eq('project_id', project.id)
    .eq('report_type', 'forensic')
    .in('status', ['published', 'coming_soon'])
    .order('published_at', { ascending: false })
    .limit(1)
    .single()

  if (!report) notFound()

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cardData = report.card_data as Record<string, any> | null
  const level = (report.risk_level || cardData?.risk_level || 'elevated').toLowerCase()
  const config = riskConfig[level] || riskConfig.elevated
  const riskScore = report.card_risk_score ?? cardData?.risk_score ?? 0

  // Locale-aware keyword/summary resolution
  const keywordsLocaleKey = `keywords_${locale}`
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const keywords: string[] =
    ((cardData as any)?.[keywordsLocaleKey]
    ?? (locale === 'ko' ? (report.card_keywords ?? cardData?.keywords_ko ?? cardData?.keywords ?? []) : []))
    || (cardData?.keywords_en ?? report.card_keywords ?? [])

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const summary =
    (report as any)[`card_summary_${locale}`]
    || report.card_summary_en
    || cardData?.summary
    || ''

  const change24h = cardData?.price_change_24h ?? cardData?.change_24h ?? 0
  const direction = cardData?.direction ?? (change24h >= 0 ? 'up' : 'down')
  const generatedAt = cardData?.generated_at || report.published_at || report.created_at

  const levelLabel =
    level === 'critical' ? t('riskCritical')
    : level === 'high' ? t('riskHigh')
    : t('riskElevated')

  // Resolve the best available PDF URL for the current locale
  const urlsByLang = report.gdrive_urls_by_lang as Record<string, string> | null
  const localizedUrl = urlsByLang?.[locale] || urlsByLang?.['en'] || null
  const primaryUrl = report.file_url || report.gdrive_url || localizedUrl
  const hasReport = !!primaryUrl

  return (
    <div className="min-h-screen">
      {/* Hero header */}
      <div className={`relative border-b ${config.border} bg-gradient-to-b from-gray-950 via-gray-950 to-transparent`}>
        <div className="max-w-5xl mx-auto px-6 pt-10 pb-12">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-8">
            <Link href={`/${locale}`} className="hover:text-indigo-400 transition-colors">
              {t('home')}
            </Link>
            <span>/</span>
            <Link href={`/${locale}/reports?type=forensic`} className="hover:text-indigo-400 transition-colors">
              {t('forensicReports')}
            </Link>
            <span>/</span>
            <span className="text-gray-300">{project.name}</span>
          </div>

          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-8">
            {/* Left: project info */}
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <span className={`px-3 py-1 rounded-lg text-xs font-bold uppercase ${config.bg} ${config.color} border ${config.border}`}>
                  🔍 {t('forensic')}
                </span>
                <span className={`px-3 py-1 rounded-lg text-xs font-bold uppercase ${config.bg} ${config.color} border ${config.border}`}>
                  ⚠ {levelLabel}
                </span>
              </div>

              <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
                {project.name}
                <span className="text-lg text-gray-500 font-normal ml-3">{project.symbol}</span>
              </h1>

              {change24h !== 0 && (
                <p className="text-lg mb-4">
                  <span className="text-gray-500 mr-2">{t('change24h')}:</span>
                  <span className={change24h >= 0 ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
                    {change24h >= 0 ? '+' : ''}{Number(change24h).toFixed(1)}%
                    {direction === 'up' ? ' ↑' : ' ↓'}
                  </span>
                </p>
              )}

              <p className="text-gray-400 text-lg leading-relaxed max-w-2xl">
                {summary}
              </p>
            </div>

            {/* Right: risk gauge */}
            <div className="flex flex-col items-center px-8 py-6 rounded-2xl bg-white/[0.03] border border-white/10 min-w-[200px]">
              <div className="relative w-24 h-24 mb-3">
                <svg className="w-24 h-24" viewBox="0 0 96 96">
                  <circle cx="48" cy="48" r="40" fill="none" stroke="#1F2937" strokeWidth="6" />
                  <circle
                    cx="48" cy="48" r="40" fill="none"
                    stroke={config.stroke}
                    strokeWidth="6" strokeLinecap="round"
                    strokeDasharray={`${(riskScore / 100) * 251.3} 251.3`}
                    transform="rotate(-90 48 48)"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className={`text-3xl font-black ${config.color}`}>{riskScore}</span>
                </div>
              </div>
              <p className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                {t('riskScore')}
              </p>
              <p className={`text-sm font-bold ${config.color} mt-1`}>
                {levelLabel} {t('risk')}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* Keywords */}
        {keywords.length > 0 && (
          <div className="mb-10">
            <h2 className="text-xl font-bold text-white mb-4">
              {t('keyFindings')}
            </h2>
            <div className="flex flex-wrap gap-3">
              {keywords.map((kw: string, i: number) => (
                <span
                  key={`${kw}-${i}`}
                  className={`px-4 py-2 rounded-xl text-sm font-semibold ${config.bg} ${config.color} border ${config.border}`}
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Report details / Coming soon */}
        <div className="rounded-2xl bg-white/[0.03] border border-white/10 p-8 mb-10">
          <h2 className="text-xl font-bold text-white mb-4">
            {t('reportTitle')}
          </h2>

          {hasReport ? (
            <div className="flex flex-col gap-4">
              {/* Primary download: locale-specific or fallback */}
              <a
                href={primaryUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-6 py-3 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-xl transition-colors w-fit"
              >
                📄 {t('viewReport')}
              </a>

              {/* Other language versions */}
              {urlsByLang && Object.keys(urlsByLang).length > 1 && (
                <div className="flex flex-wrap gap-2 mt-1">
                  <span className="text-sm text-gray-500 self-center mr-1">
                    {t('otherLanguages')}
                  </span>
                  {Object.entries(urlsByLang)
                    .filter(([lang]) => lang !== locale)
                    .map(([lang, url]) => (
                      <a
                        key={lang}
                        href={url as string}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3 py-1 text-xs font-medium bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white rounded-lg border border-white/10 transition-colors uppercase"
                      >
                        {lang}
                      </a>
                    ))}
                </div>
              )}

              {report.gdrive_url_free && (
                <a
                  href={report.gdrive_url_free}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-white/10 hover:bg-white/20 text-white font-semibold rounded-xl transition-colors w-fit"
                >
                  📄 {t('freeSummary')}
                </a>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">🔍</div>
              <p className="text-lg text-gray-400 mb-2">
                {t('comingSoonTitle')}
              </p>
              <p className="text-sm text-gray-500">
                {t('comingSoonDesc')}
              </p>
            </div>
          )}
        </div>

        {/* Report metadata */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {t('reportType')}
            </p>
            <p className="text-white font-semibold">
              {t('reportTypeName')}
            </p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {t('versionLabel')}
            </p>
            <p className="text-white font-semibold">v{report.version || 1}</p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {t('analysisDate')}
            </p>
            <p className="text-white font-semibold">
              {generatedAt
                ? new Date(generatedAt).toLocaleDateString(localeMap[locale] || 'en-US', {
                    year: 'numeric', month: 'long', day: 'numeric'
                  })
                : '—'}
            </p>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="rounded-xl bg-yellow-500/5 border border-yellow-500/20 p-6">
          <p className="text-xs text-yellow-600/80 leading-relaxed">
            ⚠ {t('disclaimer')}
          </p>
        </div>

        {/* Back link */}
        <div className="flex justify-center mt-10">
          <Link
            href={`/${locale}/reports?type=forensic`}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all font-medium"
          >
            <span>←</span>
            <span>{t('allForensicReports')}</span>
          </Link>
        </div>
      </div>
    </div>
  )
}
