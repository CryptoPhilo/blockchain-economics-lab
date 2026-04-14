'use client'

import Link from 'next/link'
import { useState } from 'react'

interface ForensicCardPreviewProps {
  _reportId: string
  slug: string
  projectName: string
  symbol: string
  change24h: number
  riskLevel: 'Critical' | 'High' | 'Elevated'
  riskScore: number
  keywords: string[]
  summaryText: string
}

const riskLevelConfig: Record<
  'Critical' | 'High' | 'Elevated',
  { bg: string; text: string; bgGauge: string }
> = {
  Critical: { bg: 'bg-red-500/20 text-red-400', text: 'text-red-400', bgGauge: 'bg-red-600' },
  High: { bg: 'bg-orange-500/20 text-orange-400', text: 'text-orange-400', bgGauge: 'bg-orange-600' },
  Elevated: { bg: 'bg-yellow-500/20 text-yellow-400', text: 'text-yellow-400', bgGauge: 'bg-yellow-600' },
}

export default function ForensicCardPreview({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _reportId,
  slug,
  projectName,
  symbol,
  change24h,
  riskLevel,
  riskScore,
  keywords,
  summaryText,
}: ForensicCardPreviewProps) {
  const [isHovering, setIsHovering] = useState(false)
  // Normalize riskLevel — DB stores lowercase ('high') but config uses capitalized ('High')
  const normalizedLevel = (riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1).toLowerCase()) as keyof typeof riskLevelConfig
  const config = riskLevelConfig[normalizedLevel] || riskLevelConfig.Elevated

  // Risk gauge angle calculation (0-180 degrees for arc)
  const gaugeAngle = (riskScore / 100) * 180

  return (
    <div
      className="relative flex flex-col p-6 rounded-2xl bg-gray-900/80 border border-red-900/30 hover:border-red-900/60 transition-all duration-300 group overflow-hidden"
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {/* Background glow effect on hover */}
      {isHovering && (
        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 bg-gradient-to-br from-red-900/20 to-transparent transition-opacity duration-300 pointer-events-none" />
      )}

      <div className="relative z-10">
        {/* Header: Risk Badge and Project Info */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white mb-1">{projectName}</h3>
            <p className="text-sm text-gray-400">{symbol}</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap ${config.bg}`}>
            ⚠ {normalizedLevel}
          </span>
        </div>

        {/* 24h Change */}
        <div className="mb-4 flex items-center gap-2">
          <span className="text-xs text-gray-500">24h Change:</span>
          <span className={`text-sm font-semibold ${change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {change24h >= 0 ? '+' : ''}
            {change24h.toFixed(2)}%
          </span>
        </div>

        {/* Risk Score Gauge (CSS Arc) */}
        <div className="mb-6 flex items-center gap-4">
          <div className="relative w-16 h-12">
            {/* Gauge background */}
            <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 60">
              {/* Arc background */}
              <path
                d="M 10 50 A 40 40 0 0 1 90 50"
                fill="none"
                stroke="rgba(107, 114, 128, 0.3)"
                strokeWidth="4"
                strokeLinecap="round"
              />
              {/* Arc fill */}
              <path
                d="M 10 50 A 40 40 0 0 1 90 50"
                fill="none"
                stroke={
                  riskLevel === 'Critical'
                    ? '#dc2626'
                    : riskLevel === 'High'
                      ? '#ea580c'
                      : '#eab308'
                }
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray={`${(gaugeAngle / 180) * 126} 126`}
              />
            </svg>
            {/* Center text */}
            <div className="absolute inset-0 flex items-center justify-center">
              <span className={`text-xs font-bold ${config.text}`}>{riskScore}</span>
            </div>
          </div>
          <div className="flex-1">
            <p className="text-xs text-gray-500">Risk Score</p>
            <p className={`text-sm font-semibold ${config.text}`}>{normalizedLevel}</p>
          </div>
        </div>

        {/* Keywords/Tags */}
        <div className="mb-4 flex flex-wrap gap-2">
          {keywords.slice(0, 3).map((keyword) => (
            <span
              key={keyword}
              className="px-2.5 py-1 rounded-full text-xs bg-red-900/40 text-red-300 border border-red-900/60"
            >
              {keyword}
            </span>
          ))}
          {keywords.length > 3 && (
            <span className="px-2.5 py-1 rounded-full text-xs bg-gray-800/40 text-gray-400">
              +{keywords.length - 3} more
            </span>
          )}
        </div>

        {/* Summary Text (2 lines max) */}
        <p className="text-sm text-gray-400 line-clamp-2 mb-6">{summaryText}</p>

        {/* CTA Button */}
        <Link
          href={`/reports/forensic/${slug}`}
          className="inline-flex items-center justify-center gap-2 w-full px-4 py-3 rounded-lg bg-red-900/30 hover:bg-red-900/50 border border-red-900/50 text-red-400 hover:text-red-300 transition-all duration-200 text-sm font-medium group/btn"
        >
          <span>Get Full Report</span>
          <span className="group-hover/btn:translate-x-1 transition-transform">→</span>
        </Link>
      </div>
    </div>
  )
}
