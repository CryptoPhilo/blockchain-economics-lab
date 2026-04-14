'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'

/**
 * ForensicSlideCards — Auto-scrolling carousel of forensic report thumbnails.
 *
 * When 3+ cards: infinite horizontal scroll (left → right loop).
 * When 1-2 cards: static grid layout.
 * Supports ko/en multilingual card content.
 */

interface ForensicSlideCardsProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  reports: any[]
  locale: string
}

const riskConfig: Record<string, { accent: string; badge: string; glow: string; stroke: string }> = {
  critical: {
    accent: 'from-red-700 to-red-900',
    badge: 'bg-red-600 text-white',
    glow: 'shadow-red-900/40',
    stroke: '#B91C1C',
  },
  high: {
    accent: 'from-orange-700 to-red-800',
    badge: 'bg-orange-600 text-white',
    glow: 'shadow-orange-900/30',
    stroke: '#EA580C',
  },
  elevated: {
    accent: 'from-yellow-700 to-orange-800',
    badge: 'bg-yellow-600 text-white',
    glow: 'shadow-yellow-900/20',
    stroke: '#CA8A04',
  },
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function SlideCard({ report, locale }: { report: any; locale: string }) {
  const tp = Array.isArray(report.tracked_projects)
    ? report.tracked_projects[0]
    : // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (report.tracked_projects as any)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cardData = report.card_data as Record<string, any> | null
  const level = (report.risk_level || cardData?.risk_level || 'elevated').toLowerCase()
  const config = riskConfig[level] || riskConfig.elevated
  const riskScore = report.card_risk_score ?? cardData?.risk_score ?? 0
  const isKo = locale === 'ko'

  // Multilingual: pick keywords by locale
  const keywords: string[] = isKo
    ? (report.card_keywords ?? cardData?.keywords_ko ?? cardData?.keywords ?? [])
    : (cardData?.keywords_en ?? report.card_keywords ?? [])

  // Multilingual: pick summary by locale
  const summary = isKo
    ? (report.card_summary_ko || report.card_summary_en || cardData?.summary || '포렌식 분석 진행 중...')
    : (report.card_summary_en || cardData?.summary || 'Forensic analysis in progress...')

  const change24h = cardData?.price_change_24h ?? cardData?.change_24h ?? 0
  const slug = tp?.slug ?? ''

  const viewLabel = isKo ? '전체 보고서 보기 →' : 'View Full Report →'
  const getLabel = isKo ? '전체 보고서 보기 →' : 'Get Full Report →'
  const riskLabel = isKo ? '위험 점수' : 'Risk Score'
  const riskLevelLabel = isKo
    ? `${level === 'critical' ? '심각' : level === 'high' ? '높음' : '경계'} 위험`
    : `${level.charAt(0).toUpperCase() + level.slice(1)} Risk`

  // If a real thumbnail URL exists, show the actual image
  if (report.card_thumbnail_url) {
    return (
      <Link
        href={`/${locale}/reports/forensic/${slug}`}
        className="group block relative overflow-hidden rounded-2xl shadow-2xl hover:shadow-3xl transition-all duration-500 hover:scale-[1.02] flex-shrink-0 w-[340px] md:w-[400px]"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={report.card_thumbnail_url}
          alt={`${tp?.name ?? 'Project'} Forensic Report`}
          className="w-full aspect-[16/9] object-cover"
        />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all duration-300 flex items-center justify-center">
          <span className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 px-6 py-3 bg-red-600/90 text-white font-semibold rounded-lg backdrop-blur-sm">
            {viewLabel}
          </span>
        </div>
      </Link>
    )
  }

  // CSS-based slide cover preview
  return (
    <Link
      href={`/${locale}/reports/forensic/${slug}`}
      className="group block relative overflow-hidden rounded-2xl transition-all duration-500 hover:scale-[1.02] flex-shrink-0 w-[340px] md:w-[400px]"
    >
      <div
        className={`relative aspect-[16/9] bg-gradient-to-br from-[#F5F1EB] to-[#EDE8DF] border-2 border-[#D4C5A9] shadow-2xl ${config.glow} overflow-hidden`}
      >
        {/* CONFIDENTIAL watermark */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
          <span
            className="text-[48px] lg:text-[64px] font-black text-red-200/15 tracking-[0.2em] whitespace-nowrap select-none"
            style={{ transform: 'rotate(-25deg)' }}
          >
            CONFIDENTIAL
          </span>
        </div>

        {/* Top red accent bar */}
        <div className={`absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r ${config.accent}`} />

        {/* BCE Lab logo */}
        <div className="absolute top-4 left-5 flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-[#2D2D2D] flex items-center justify-center">
            <span className="text-[10px] font-bold text-[#F5F1EB]">B</span>
          </div>
          <span className="text-[11px] font-semibold text-[#777] tracking-wider">
            BCE LAB FORENSIC
          </span>
        </div>

        {/* Risk badge */}
        <div className="absolute top-4 right-5">
          <span className={`px-3 py-1 rounded text-xs font-bold uppercase tracking-wider ${config.badge}`}>
            ⚠ {level}
          </span>
        </div>

        {/* Main content */}
        <div className="absolute inset-0 flex flex-col justify-center px-8 pt-12">
          <div className="mb-3">
            <h3 className="text-xl lg:text-2xl font-black text-[#1A1A1A] leading-tight">
              {tp?.name ?? 'Unknown Project'}
            </h3>
            <p className="text-xs font-semibold text-[#777] mt-1">
              {tp?.symbol ?? ''}{' '}
              {change24h !== 0 && (
                <span className={change24h >= 0 ? 'text-green-700' : 'text-red-700'}>
                  {change24h >= 0 ? '+' : ''}{Number(change24h).toFixed(1)}%
                </span>
              )}
            </p>
          </div>

          {/* Risk Score gauge */}
          <div className="flex items-center gap-3 mb-3">
            <div className="relative w-11 h-11">
              <svg className="w-11 h-11" viewBox="0 0 44 44">
                <circle cx="22" cy="22" r="19" fill="none" stroke="#E0D8CC" strokeWidth="3" />
                <circle
                  cx="22" cy="22" r="19" fill="none"
                  stroke={config.stroke}
                  strokeWidth="3" strokeLinecap="round"
                  strokeDasharray={`${(riskScore / 100) * 119.4} 119.4`}
                  transform="rotate(-90 22 22)"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-xs font-black text-[#1A1A1A]">{riskScore}</span>
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold text-[#777] uppercase tracking-wider">{riskLabel}</p>
              <p className="text-sm font-bold text-[#B91C1C]">{riskLevelLabel}</p>
            </div>
          </div>

          {/* Keywords */}
          <div className="flex flex-wrap gap-1.5 mb-2">
            {keywords.slice(0, 4).map((kw: string, i: number) => (
              <span key={`${kw}-${i}`} className="px-2 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-800 border border-red-200">
                {kw}
              </span>
            ))}
          </div>

          <p className="text-xs text-[#444] line-clamp-1 max-w-[80%]">{summary}</p>
        </div>

        {/* Bottom bar */}
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-[#2D2D2D] flex items-center px-5 justify-between">
          <span className="text-[10px] text-[#999] font-mono">bcelab.xyz</span>
          <span className="text-[10px] text-[#999]">Blockchain Economics Lab</span>
        </div>

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-all duration-300 flex items-center justify-center">
          <span className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 px-5 py-2.5 bg-red-700/90 text-white font-semibold rounded-lg text-sm backdrop-blur-sm shadow-lg">
            {getLabel}
          </span>
        </div>
      </div>
    </Link>
  )
}

/**
 * Infinite auto-scrolling carousel.
 * Duplicates cards to create seamless loop effect.
 * Pauses on hover so users can click.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CarouselTrack({ reports, locale }: { reports: any[]; locale: string }) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [isPaused, setIsPaused] = useState(false)

  // We duplicate the list to create the infinite illusion
  // 3 copies: enough buffer for seamless scroll
  const tripled = [...reports, ...reports, ...reports]

  useEffect(() => {
    const track = trackRef.current
    if (!track) return

    let animId: number
    // Speed: pixels per frame (~60fps → ~1px/frame ≈ 60px/s)
    const speed = 0.8

    const step = () => {
      if (!isPaused && track) {
        track.scrollLeft += speed
        // When we've scrolled past the first copy, jump back seamlessly
        const singleSetWidth = track.scrollWidth / 3
        if (track.scrollLeft >= singleSetWidth * 2) {
          track.scrollLeft -= singleSetWidth
        }
      }
      animId = requestAnimationFrame(step)
    }

    // Start at the beginning of the second copy (middle) for seamless left scroll
    const singleSetWidth = track.scrollWidth / 3
    track.scrollLeft = singleSetWidth

    animId = requestAnimationFrame(step)
    return () => cancelAnimationFrame(animId)
  }, [isPaused])

  return (
    <div
      ref={trackRef}
      className="flex gap-6 overflow-x-hidden py-2 px-4"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      style={{ scrollBehavior: 'auto' }}
    >
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {tripled.map((r: any, idx: number) => (
        <SlideCard key={`${r.id}-${idx}`} report={r} locale={locale} />
      ))}
    </div>
  )
}

export default function ForensicSlideCards({ reports, locale }: ForensicSlideCardsProps) {
  if (!reports || reports.length === 0) return null

  const isKo = locale === 'ko'

  return (
    <section className="py-16 md:py-20">
      <div className="max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 text-sm mb-4">
            <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
            {isKo ? '실시간 포렌식 인텔리전스' : 'Live Forensic Intelligence'}
          </div>
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
            {isKo ? '최신 포렌식 보고서' : 'Latest Forensic Reports'}
          </h2>
          <p className="text-lg text-gray-400">
            {isKo
              ? 'AI 기반 온체인 포렌식 & 시장 이상 탐지'
              : 'AI-powered on-chain forensics & market anomaly detection'}
          </p>
        </div>
      </div>

      {/* Carousel or static grid */}
      {reports.length >= 3 ? (
        <CarouselTrack reports={reports} locale={locale} />
      ) : reports.length === 2 ? (
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {reports.map((r: any) => (
              <SlideCard key={r.id} report={r} locale={locale} />
            ))}
          </div>
        </div>
      ) : (
        <div className="max-w-2xl mx-auto px-6">
          <SlideCard report={reports[0]} locale={locale} />
        </div>
      )}

      {/* CTA */}
      <div className="flex justify-center mt-10">
        <Link
          href={`/${locale}/reports?type=forensic`}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-red-900/30 hover:bg-red-900/50 border border-red-900/50 text-red-400 hover:text-red-300 transition-all duration-200 font-medium group"
        >
          <span>{isKo ? '전체 포렌식 보고서 보기' : 'View All Forensic Reports'}</span>
          <span className="group-hover:translate-x-1 transition-transform">→</span>
        </Link>
      </div>
    </section>
  )
}
