'use client'

import Link from 'next/link'
import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { cleanCardSummary } from '@/lib/report-summary'

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
  // tracked_projects is now a single object via !inner join (not an array)
  const tp = Array.isArray(report.tracked_projects)
    ? report.tracked_projects[0]
    : (report.tracked_projects as Record<string, unknown> | null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cardData = report.card_data as Record<string, any> | null
  const level = (report.risk_level || cardData?.risk_level || 'elevated').toLowerCase()
  const config = riskConfig[level] || riskConfig.elevated
  const riskScore = report.card_risk_score ?? cardData?.risk_score ?? 0
  // Multilingual: pick keywords by locale (7 languages)
  const keywordsByLang = cardData?.keywords_by_lang as Record<string, string[]> | undefined
  const localizedKeywords = keywordsByLang?.[locale] ?? cardData?.[`keywords_${locale}`]
  const sourceKeywords = report.language === locale ? (report.card_keywords ?? cardData?.keywords) : undefined
  const englishKeywords = locale === 'en' ? (cardData?.keywords_en ?? report.card_keywords) : undefined
  const keywords: string[] =
    localizedKeywords ?? sourceKeywords ?? englishKeywords ?? []

  // Multilingual: pick summary by locale (7 languages)
  const summaryByLang = cardData?.summary_by_lang as Record<string, string> | undefined
  const defaultSummary: Record<string, string> = {
    ko: '포렌식 분석 진행 중...', en: 'Forensic analysis in progress...',
    ja: 'フォレンジック分析進行中...', zh: '取证分析进行中...',
    fr: 'Analyse forensique en cours...', es: 'Análisis forense en curso...',
    de: 'Forensische Analyse läuft...',
  }
  const localizedSummary = summaryByLang?.[locale] || report[`card_summary_${locale}`]
  const sourceSummary = report.language === locale ? (cardData?.summary || report.card_summary_en || '') : ''
  const englishSummary = locale === 'en' ? (summaryByLang?.en || report.card_summary_en || '') : ''
  const summary = cleanCardSummary(
    localizedSummary || sourceSummary || englishSummary || (defaultSummary[locale] || defaultSummary.en),
  )

  const change24h = cardData?.price_change_24h ?? cardData?.change_24h ?? 0
  const slug = tp?.slug ?? ''

  const viewLabels: Record<string, string> = {
    ko: '전체 보고서 보기 →', en: 'View Full Report →',
    ja: '完全レポートを見る →', zh: '查看完整报告 →',
    fr: 'Voir le rapport complet →', es: 'Ver informe completo →',
    de: 'Vollständigen Bericht ansehen →',
  }
  const riskLabels: Record<string, string> = {
    ko: '위험 점수', en: 'Risk Score',
    ja: 'リスクスコア', zh: '风险评分',
    fr: 'Score de risque', es: 'Puntuación de riesgo',
    de: 'Risikobewertung',
  }
  const riskLevelNames: Record<string, Record<string, string>> = {
    critical: { ko: '심각 위험', en: 'Critical Risk', ja: '重大リスク', zh: '严重风险', fr: 'Risque critique', es: 'Riesgo crítico', de: 'Kritisches Risiko' },
    high:     { ko: '높음 위험', en: 'High Risk', ja: '高リスク', zh: '高风险', fr: 'Risque élevé', es: 'Riesgo alto', de: 'Hohes Risiko' },
    elevated: { ko: '경계 위험', en: 'Elevated Risk', ja: '警戒リスク', zh: '警戒风险', fr: 'Risque modéré', es: 'Riesgo moderado', de: 'Erhöhtes Risiko' },
    moderate: { ko: '보통 위험', en: 'Moderate Risk', ja: '中程度リスク', zh: '中等风险', fr: 'Risque modéré', es: 'Riesgo moderado', de: 'Mäßiges Risiko' },
  }
  const viewLabel = viewLabels[locale] || viewLabels.en
  const getLabel = viewLabel
  const riskLabel = riskLabels[locale] || riskLabels.en
  const riskLevelLabel = riskLevelNames[level]?.[locale] || riskLevelNames[level]?.en || `${level} Risk`

  // Always use CSS-based card (GDrive thumbnail URLs are unreliable)
  return (
    <Link
      href={`/${locale}/reports/forensic/${slug}`}
      className="group block w-full overflow-hidden rounded-2xl transition-all duration-500 hover:scale-[1.01]"
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

export default function ForensicSlideCards({ reports, locale }: ForensicSlideCardsProps) {
  const isKo = locale === 'ko'
  const [activeIndex, setActiveIndex] = useState(0)
  const visibleReports = reports?.slice(0, 8) ?? []
  const hasMultipleReports = visibleReports.length > 1
  const goToPrevious = () => setActiveIndex((index) => (index === 0 ? visibleReports.length - 1 : index - 1))
  const goToNext = () => setActiveIndex((index) => (index + 1) % visibleReports.length)

  if (visibleReports.length === 0) return null

  return (
    <section className="bg-gray-950 px-6 pb-16 pt-10 md:pb-20 md:pt-14">
      <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[minmax(0,0.86fr)_minmax(360px,1.14fr)] lg:items-center">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">
            {isKo ? '새로 발행된 보고서' : 'Newly Published Reports'}
          </p>
          <h1 className="mt-4 text-4xl font-bold leading-tight text-white md:text-6xl">
            {isKo ? '최신 ECON, MAT, FOR 리포트' : 'Latest ECON, MAT, and FOR Reports'}
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-gray-400 md:text-lg">
            {isKo
              ? '새로 발행된 리포트 표지를 한 장씩 크게 확인하세요.'
              : 'Browse newly published report covers one at a time.'}
          </p>

          <Link
            href={`/${locale}/reports`}
            className="mt-8 inline-flex rounded-lg border border-white/15 px-5 py-3 text-sm font-semibold text-gray-200 transition-colors hover:border-white/30 hover:text-white"
          >
            {isKo ? '전체 리포트 보기' : 'View all reports'}
          </Link>
        </div>

        <div className="min-w-0">
          <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-4 md:p-5">
            <SlideCard report={visibleReports[activeIndex]} locale={locale} />

            {hasMultipleReports && (
              <div className="absolute inset-x-6 top-1/2 flex -translate-y-1/2 justify-between">
                <button
                  type="button"
                  onClick={goToPrevious}
                  className="grid h-10 w-10 place-items-center rounded-full border border-white/15 bg-gray-950/80 text-white transition-colors hover:border-white/30"
                  aria-label={isKo ? '이전 리포트' : 'Previous report'}
                >
                  <ChevronLeft size={20} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={goToNext}
                  className="grid h-10 w-10 place-items-center rounded-full border border-white/15 bg-gray-950/80 text-white transition-colors hover:border-white/30"
                  aria-label={isKo ? '다음 리포트' : 'Next report'}
                >
                  <ChevronRight size={20} aria-hidden="true" />
                </button>
              </div>
            )}
          </div>

          {hasMultipleReports && (
            <div className="mt-5 flex justify-center gap-2">
              {visibleReports.map((report, index) => (
                <button
                  key={report.id}
                  type="button"
                  onClick={() => setActiveIndex(index)}
                  className={`h-2.5 rounded-full transition-all ${
                    index === activeIndex ? 'w-8 bg-white' : 'w-2.5 bg-white/25 hover:bg-white/45'
                  }`}
                  aria-label={isKo ? `${index + 1}번째 리포트 보기` : `Show report ${index + 1}`}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
