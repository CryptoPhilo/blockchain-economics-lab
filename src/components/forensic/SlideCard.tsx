'use client'

import Link from 'next/link'
import { RISK_CONFIG, FORENSIC_LABELS, getLabel, type RiskLevel } from '@/lib/constants/forensic'
import type { HomepageForensicProject, HomepageForensicReport, SupportedLanguage } from '@/lib/types'

interface SlideCardProps {
  report: HomepageForensicReport
  locale: SupportedLanguage
}

export default function SlideCard({ report, locale }: SlideCardProps) {
  const rawProject = report.tracked_projects ?? report.project
  const tp: HomepageForensicProject | null = Array.isArray(rawProject)
    ? rawProject[0]
    : rawProject ?? null

  const cardData = report.card_data ?? null
  const level = (report.risk_level || cardData?.risk_level || 'elevated').toLowerCase() as RiskLevel
  const config = RISK_CONFIG[level] || RISK_CONFIG.elevated
  const riskScore = report.card_risk_score ?? cardData?.risk_score ?? 0

  const keywordsByLang = cardData?.keywords_by_lang as Record<string, string[]> | undefined
  const keywords: string[] =
    keywordsByLang?.[locale] ??
    (locale === 'ko'
      ? (report.card_keywords ?? cardData?.keywords ?? [])
      : (cardData?.keywords_en ?? report.card_keywords ?? []))

  const summaryByLang = cardData?.summary_by_lang as Record<string, string> | undefined
  const summary =
    summaryByLang?.[locale] ??
    ((locale === 'ko'
      ? (report.card_summary_ko || report.card_summary_en || '')
      : (report.card_summary_en || '')) ||
    getLabel(FORENSIC_LABELS.defaultSummary, locale))

  const change24h = cardData?.price_change_24h ?? cardData?.change_24h ?? 0
  const slug = tp?.slug ?? ''

  const viewLabel = getLabel(FORENSIC_LABELS.viewReport, locale)
  const riskLabel = getLabel(FORENSIC_LABELS.riskScore, locale)
  const riskLevelLabel = getLabel(FORENSIC_LABELS.riskLevel[level] || FORENSIC_LABELS.riskLevel.elevated, locale)

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
            {viewLabel}
          </span>
        </div>
      </div>
    </Link>
  )
}
