import { createServerSupabaseClient } from '@/lib/supabase-server'
import Link from 'next/link'
import { notFound } from 'next/navigation'

interface Props {
  params: Promise<{ locale: string; slug: string }>
}

const riskConfig: Record<string, { color: string; bg: string; border: string; stroke: string }> = {
  critical: { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', stroke: '#EF4444' },
  high: { color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', stroke: '#F97316' },
  elevated: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', stroke: '#EAB308' },
}

export default async function ForensicReportPage({ params }: Props) {
  const { locale, slug } = await params
  const isKo = locale === 'ko'
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

  const keywords: string[] = isKo
    ? (report.card_keywords ?? cardData?.keywords_ko ?? cardData?.keywords ?? [])
    : (cardData?.keywords_en ?? report.card_keywords ?? [])

  const summary = isKo
    ? (report.card_summary_ko || report.card_summary_en || cardData?.summary || '')
    : (report.card_summary_en || cardData?.summary || '')

  const change24h = cardData?.price_change_24h ?? cardData?.change_24h ?? 0
  const direction = cardData?.direction ?? (change24h >= 0 ? 'up' : 'down')
  const generatedAt = cardData?.generated_at || report.published_at || report.created_at

  const levelLabel = isKo
    ? (level === 'critical' ? '심각' : level === 'high' ? '높음' : '경계')
    : (level.charAt(0).toUpperCase() + level.slice(1))

  return (
    <div className="min-h-screen">
      {/* Hero header */}
      <div className={`relative border-b ${config.border} bg-gradient-to-b from-gray-950 via-gray-950 to-transparent`}>
        <div className="max-w-5xl mx-auto px-6 pt-10 pb-12">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-8">
            <Link href={`/${locale}`} className="hover:text-indigo-400 transition-colors">
              {isKo ? '홈' : 'Home'}
            </Link>
            <span>/</span>
            <Link href={`/${locale}/reports?type=forensic`} className="hover:text-indigo-400 transition-colors">
              {isKo ? '포렌식 보고서' : 'Forensic Reports'}
            </Link>
            <span>/</span>
            <span className="text-gray-300">{project.name}</span>
          </div>

          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-8">
            {/* Left: project info */}
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <span className={`px-3 py-1 rounded-lg text-xs font-bold uppercase ${config.bg} ${config.color} border ${config.border}`}>
                  🔍 {isKo ? '포렌식' : 'FORENSIC'}
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
                  <span className="text-gray-500 mr-2">{isKo ? '24시간 변동' : '24h Change'}:</span>
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
                {isKo ? '위험 점수' : 'Risk Score'}
              </p>
              <p className={`text-sm font-bold ${config.color} mt-1`}>
                {levelLabel} {isKo ? '위험' : 'Risk'}
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
              {isKo ? '주요 발견 키워드' : 'Key Findings'}
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
            {isKo ? '포렌식 분석 보고서' : 'Forensic Analysis Report'}
          </h2>

          {report.file_url || report.gdrive_url ? (
            <div className="flex flex-col gap-4">
              {report.gdrive_url && (
                <a
                  href={report.gdrive_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-xl transition-colors w-fit"
                >
                  📄 {isKo ? '전체 보고서 보기 (Google Drive)' : 'View Full Report (Google Drive)'}
                </a>
              )}
              {report.gdrive_url_free && (
                <a
                  href={report.gdrive_url_free}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-white/10 hover:bg-white/20 text-white font-semibold rounded-xl transition-colors w-fit"
                >
                  📄 {isKo ? '무료 요약 보기' : 'View Free Summary'}
                </a>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">🔍</div>
              <p className="text-lg text-gray-400 mb-2">
                {isKo
                  ? '전체 포렌식 보고서가 곧 공개됩니다.'
                  : 'Full forensic report coming soon.'}
              </p>
              <p className="text-sm text-gray-500">
                {isKo
                  ? '위 요약은 AI 포렌식 분석의 핵심 발견을 담고 있습니다. 전체 보고서에는 온체인 데이터 분석, 거래소 유출입 패턴, 파생상품 시장 분석이 포함됩니다.'
                  : 'The summary above contains key findings from our AI forensic analysis. The full report will include on-chain data analysis, exchange flow patterns, and derivatives market analysis.'}
              </p>
            </div>
          )}
        </div>

        {/* Report metadata */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {isKo ? '보고서 유형' : 'Report Type'}
            </p>
            <p className="text-white font-semibold">
              {isKo ? '포렌식 리스크 분석' : 'Forensic Risk Analysis'}
            </p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {isKo ? '버전' : 'Version'}
            </p>
            <p className="text-white font-semibold">v{report.version || 1}</p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {isKo ? '분석 일시' : 'Analysis Date'}
            </p>
            <p className="text-white font-semibold">
              {generatedAt
                ? new Date(generatedAt).toLocaleDateString(isKo ? 'ko-KR' : 'en-US', {
                    year: 'numeric', month: 'long', day: 'numeric'
                  })
                : '—'}
            </p>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="rounded-xl bg-yellow-500/5 border border-yellow-500/20 p-6">
          <p className="text-xs text-yellow-600/80 leading-relaxed">
            {isKo
              ? '⚠ 면책 조항: 이 포렌식 분석은 AI 기반 온체인 데이터 분석과 시장 패턴 감지를 통해 생성되었습니다. 투자 조언이 아니며, 모든 투자 결정은 본인의 책임 하에 이루어져야 합니다. 과거의 패턴이 미래의 결과를 보장하지 않습니다.'
              : '⚠ Disclaimer: This forensic analysis is generated through AI-powered on-chain data analysis and market pattern detection. This is not investment advice. All investment decisions should be made at your own risk. Past patterns do not guarantee future results.'}
          </p>
        </div>

        {/* Back link */}
        <div className="flex justify-center mt-10">
          <Link
            href={`/${locale}/reports?type=forensic`}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all font-medium"
          >
            <span>←</span>
            <span>{isKo ? '전체 포렌식 보고서' : 'All Forensic Reports'}</span>
          </Link>
        </div>
      </div>
    </div>
  )
}
