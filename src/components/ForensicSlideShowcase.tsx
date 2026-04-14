import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'

/**
 * ForensicSlideShowcase — Homepage center-stage component
 *
 * Displays forensic report "slide thumbnails" — graphical first-page previews
 * that mimic the cover slide from gen_slide_html_for.py (beige + forensic red theme).
 *
 * When card_thumbnail_url exists → renders actual thumbnail image
 * When not available → renders a CSS-based slide cover preview with:
 *   - CONFIDENTIAL watermark
 *   - Risk level badge (Critical/High/Elevated)
 *   - Project name + symbol
 *   - Risk score gauge
 *   - Key findings keywords
 */

interface ForensicReport {
  id: string
  project_id: string
  risk_level: string | null
  card_data: Record<string, any> | null
  card_summary_en: string | null
  card_summary_ko: string | null
  card_keywords: string[] | null
  card_risk_score: number | null
  card_thumbnail_url: string | null
  tracked_projects: {
    id: string
    name: string
    slug: string
    symbol: string
  }
}

// Risk level visual config (matching forensic slide theme)
const riskConfig: Record<string, { accent: string; badge: string; glow: string }> = {
  critical: {
    accent: 'from-red-700 to-red-900',
    badge: 'bg-red-600 text-white',
    glow: 'shadow-red-900/40',
  },
  high: {
    accent: 'from-orange-700 to-red-800',
    badge: 'bg-orange-600 text-white',
    glow: 'shadow-orange-900/30',
  },
  elevated: {
    accent: 'from-yellow-700 to-orange-800',
    badge: 'bg-yellow-600 text-white',
    glow: 'shadow-yellow-900/20',
  },
}

function SlidePreviewCard({
  report,
  locale,
}: {
  report: ForensicReport
  locale?: string
}) {
  const tp = Array.isArray(report.tracked_projects)
    ? report.tracked_projects[0]
    : (report.tracked_projects as any)
  const cardData = report.card_data as Record<string, any> | null
  const level = (report.risk_level || cardData?.risk_level || 'elevated').toLowerCase()
  const config = riskConfig[level] || riskConfig.elevated
  const riskScore = report.card_risk_score ?? cardData?.risk_score ?? 0
  const keywords = report.card_keywords ?? cardData?.keywords_en ?? []
  const summary =
    report.card_summary_en ||
    cardData?.summary ||
    'Forensic analysis in progress...'
  const change24h = cardData?.price_change_24h ?? cardData?.change_24h ?? 0
  const slug = tp?.slug ?? ''

  // If a real thumbnail URL exists, show the actual image
  if (report.card_thumbnail_url) {
    return (
      <Link
        href={`/${locale || 'en'}/reports/forensic/${slug}`}
        className="group block relative overflow-hidden rounded-2xl shadow-2xl hover:shadow-3xl transition-all duration-500 hover:scale-[1.02]"
      >
        <img
          src={report.card_thumbnail_url}
          alt={`${tp?.name ?? 'Project'} Forensic Report`}
          className="w-full aspect-[16/9] object-cover"
        />
        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all duration-300 flex items-center justify-center">
          <span className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 px-6 py-3 bg-red-600/90 text-white font-semibold rounded-lg backdrop-blur-sm">
            View Full Report →
          </span>
        </div>
      </Link>
    )
  }

  // CSS-based slide cover preview (mimics gen_slide_html_for.py cover slide)
  return (
    <Link
      href={`/${locale || 'en'}/reports/forensic/${slug}`}
      className="group block relative overflow-hidden rounded-2xl transition-all duration-500 hover:scale-[1.02]"
    >
      {/* Slide container — 16:9 aspect ratio like actual slides */}
      <div
        className={`relative aspect-[16/9] bg-gradient-to-br from-[#F5F1EB] to-[#EDE8DF] border-2 border-[#D4C5A9] shadow-2xl ${config.glow} overflow-hidden`}
      >
        {/* CONFIDENTIAL watermark (rotated) */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
          <span
            className="text-[80px] font-black text-red-200/15 tracking-[0.3em] whitespace-nowrap select-none"
            style={{ transform: 'rotate(-25deg)' }}
          >
            CONFIDENTIAL
          </span>
        </div>

        {/* Top red accent bar */}
        <div className={`absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r ${config.accent}`} />

        {/* BCE Lab logo area */}
        <div className="absolute top-4 left-5 flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-[#2D2D2D] flex items-center justify-center">
            <span className="text-[10px] font-bold text-[#F5F1EB]">B</span>
          </div>
          <span className="text-[11px] font-semibold text-[#777] tracking-wider">
            BCE LAB FORENSIC
          </span>
        </div>

        {/* Risk level badge — top right */}
        <div className="absolute top-4 right-5">
          <span
            className={`px-3 py-1 rounded text-xs font-bold uppercase tracking-wider ${config.badge}`}
          >
            ⚠ {level}
          </span>
        </div>

        {/* Main content area */}
        <div className="absolute inset-0 flex flex-col justify-center px-8 pt-12">
          {/* Project name + symbol */}
          <div className="mb-3">
            <h3 className="text-2xl md:text-3xl font-black text-[#1A1A1A] leading-tight">
              {tp?.name ?? 'Unknown Project'}
            </h3>
            <p className="text-sm font-semibold text-[#777] mt-1">
              {tp?.symbol ?? ''}{' '}
              {change24h !== 0 && (
                <span
                  className={
                    change24h >= 0 ? 'text-green-700' : 'text-red-700'
                  }
                >
                  {change24h >= 0 ? '+' : ''}
                  {Number(change24h).toFixed(1)}%
                </span>
              )}
            </p>
          </div>

          {/* Risk Score gauge */}
          <div className="flex items-center gap-4 mb-3">
            <div className="relative w-14 h-14">
              <svg className="w-14 h-14" viewBox="0 0 56 56">
                <circle
                  cx="28"
                  cy="28"
                  r="24"
                  fill="none"
                  stroke="#E0D8CC"
                  strokeWidth="4"
                />
                <circle
                  cx="28"
                  cy="28"
                  r="24"
                  fill="none"
                  stroke={
                    level === 'critical'
                      ? '#B91C1C'
                      : level === 'high'
                        ? '#EA580C'
                        : '#CA8A04'
                  }
                  strokeWidth="4"
                  strokeLinecap="round"
                  strokeDasharray={`${(riskScore / 100) * 150.8} 150.8`}
                  transform="rotate(-90 28 28)"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-sm font-black text-[#1A1A1A]">
                  {riskScore}
                </span>
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold text-[#777] uppercase tracking-wider">
                Risk Score
              </p>
              <p className="text-sm font-bold text-[#B91C1C]">
                {level.charAt(0).toUpperCase() + level.slice(1)} Risk
              </p>
            </div>
          </div>

          {/* Keywords */}
          <div className="flex flex-wrap gap-1.5 mb-2">
            {keywords.slice(0, 4).map((kw: string) => (
              <span
                key={kw}
                className="px-2 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-800 border border-red-200"
              >
                {kw}
              </span>
            ))}
          </div>

          {/* Summary (1 line) */}
          <p className="text-xs text-[#444] line-clamp-1 max-w-[80%]">
            {summary}
          </p>
        </div>

        {/* Bottom decorative bar */}
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-[#2D2D2D] flex items-center px-5 justify-between">
          <span className="text-[10px] text-[#999] font-mono">
            bcelab.xyz
          </span>
          <span className="text-[10px] text-[#999]">
            Blockchain Economics Lab
          </span>
        </div>

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-all duration-300 flex items-center justify-center">
          <span className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 px-5 py-2.5 bg-red-700/90 text-white font-semibold rounded-lg text-sm backdrop-blur-sm shadow-lg">
            Get Full Report →
          </span>
        </div>
      </div>
    </Link>
  )
}

export default async function ForensicSlideShowcase() {
  try {
    const supabase = await createServerSupabaseClient()

    const { data: reports, error } = await supabase
      .from('project_reports')
      .select(
        `
        id,
        project_id,
        risk_level,
        card_data,
        card_summary_en,
        card_summary_ko,
        card_keywords,
        card_risk_score,
        card_thumbnail_url,
        tracked_projects!inner(
          id, name, slug, symbol
        )
      `
      )
      .eq('report_type', 'forensic')
      .in('status', ['published', 'coming_soon'])
      .in('card_qa_status', ['approved', 'pending'])
      .not('card_data', 'is', null)
      .order('published_at', { ascending: false })
      .limit(3)

    if (error || !reports || reports.length === 0) {
      return null
    }

    const validReports = reports.filter(
      (r) => r.tracked_projects !== null && r.card_data !== null
    )

    if (validReports.length === 0) return null

    return (
      <section className="py-16 md:py-20 px-6">
        <div className="max-w-6xl mx-auto">
          {/* Section header */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 text-sm mb-4">
              <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
              Live Forensic Intelligence
            </div>
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
              Latest Forensic Reports
            </h2>
            <p className="text-lg text-gray-400">
              AI-powered on-chain forensics & market anomaly detection
            </p>
          </div>

          {/* Slide thumbnails grid — responsive: 1 col mobile, featured+2 on desktop */}
          {validReports.length === 1 ? (
            /* Single report: centered large card */
            <div className="max-w-2xl mx-auto">
              <SlidePreviewCard report={validReports[0] as unknown as ForensicReport} />
            </div>
          ) : validReports.length === 2 ? (
            /* Two reports: side by side */
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {validReports.map((r) => (
                <SlidePreviewCard key={r.id} report={r as unknown as ForensicReport} />
              ))}
            </div>
          ) : (
            /* Three reports: featured hero + 2 smaller */
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
              {/* Featured (large) */}
              <div className="lg:col-span-3">
                <SlidePreviewCard report={validReports[0] as unknown as ForensicReport} />
              </div>
              {/* Secondary pair */}
              <div className="lg:col-span-2 flex flex-col gap-6">
                {validReports.slice(1, 3).map((r) => (
                  <SlidePreviewCard key={r.id} report={r as unknown as ForensicReport} />
                ))}
              </div>
            </div>
          )}

          {/* CTA */}
          <div className="flex justify-center mt-10">
            <Link
              href="/reports?type=forensic"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-red-900/30 hover:bg-red-900/50 border border-red-900/50 text-red-400 hover:text-red-300 transition-all duration-200 font-medium group"
            >
              <span>View All Forensic Reports</span>
              <span className="group-hover:translate-x-1 transition-transform">
                →
              </span>
            </Link>
          </div>
        </div>
      </section>
    )
  } catch (error) {
    console.error('[ForensicSlideShowcase] Error:', error)
    return null
  }
}
