'use client'

interface ScoreData {
  technology: number
  business: number
  tokenomics: number
  governance: number
  community: number
  compliance: number
  narrative: number
}

interface MaturityScoreRadarProps {
  scores: ScoreData
  overallScore: number
  projectName: string
  threatLevel?: 'clear' | 'watch' | 'caution' | 'warning' | 'critical'
  compact?: boolean
}

const AXES = [
  { key: 'technology', label: 'Tech', weight: '20%' },
  { key: 'business', label: 'Biz', weight: '20%' },
  { key: 'tokenomics', label: 'Token', weight: '15%' },
  { key: 'governance', label: 'Gov', weight: '10%' },
  { key: 'community', label: 'Comm', weight: '10%' },
  { key: 'compliance', label: 'Comp', weight: '10%' },
  { key: 'narrative', label: 'Narr', weight: '15%' },
] as const

const threatConfig = {
  clear: { emoji: '🟢', label: 'CLEAR', color: 'text-green-400', bg: 'bg-green-500/10' },
  watch: { emoji: '🟡', label: 'WATCH', color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  caution: { emoji: '🟠', label: 'CAUTION', color: 'text-orange-400', bg: 'bg-orange-500/10' },
  warning: { emoji: '🔴', label: 'WARNING', color: 'text-red-400', bg: 'bg-red-500/10' },
  critical: { emoji: '⚫', label: 'CRITICAL', color: 'text-red-600', bg: 'bg-red-600/10' },
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-400'
  if (score >= 60) return 'text-yellow-400'
  if (score >= 40) return 'text-orange-400'
  return 'text-red-400'
}

function getScoreBarColor(score: number): string {
  if (score >= 80) return 'bg-green-500'
  if (score >= 60) return 'bg-yellow-500'
  if (score >= 40) return 'bg-orange-500'
  return 'bg-red-500'
}

export default function MaturityScoreRadar({
  scores,
  overallScore,
  projectName,
  threatLevel = 'clear',
  compact = false,
}: MaturityScoreRadarProps) {
  const threat = threatConfig[threatLevel]

  if (compact) {
    return (
      <div className="flex items-center gap-3">
        <div className={`text-2xl font-bold ${getScoreColor(overallScore)}`}>
          {overallScore.toFixed(1)}
        </div>
        <div className="text-xs text-gray-500">/ 100</div>
        <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${threat.bg} ${threat.color}`}>
          {threat.emoji} {threat.label}
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-bold text-white">BCE Maturity Score™</h3>
          <p className="text-sm text-gray-500">{projectName}</p>
        </div>
        <div className="text-right">
          <div className={`text-3xl font-bold ${getScoreColor(overallScore)}`}>
            {overallScore.toFixed(1)}
          </div>
          <div className="text-xs text-gray-500">/ 100</div>
        </div>
      </div>

      {/* Threat Level */}
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${threat.bg} mb-6`}>
        <span>{threat.emoji}</span>
        <span className={`text-sm font-medium ${threat.color}`}>
          Threat Level: {threat.label}
        </span>
      </div>

      {/* 7-Axis Scores */}
      <div className="space-y-3">
        {AXES.map(({ key, label, weight }) => {
          const score = scores[key as keyof ScoreData] || 0
          return (
            <div key={key} className="flex items-center gap-3">
              <div className="w-14 text-xs text-gray-500 text-right">{label}</div>
              <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                <div
                  className={`h-full ${getScoreBarColor(score)} rounded-full transition-all duration-500`}
                  style={{ width: `${score}%` }}
                />
              </div>
              <div className={`w-10 text-right text-sm font-medium ${getScoreColor(score)}`}>
                {score.toFixed(0)}
              </div>
              <div className="w-10 text-right text-xs text-gray-600">{weight}</div>
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between">
        <span className="text-xs text-gray-600">7-Axis Weighted Assessment</span>
        <span className="text-xs text-indigo-500">360° Project Intelligence</span>
      </div>
    </div>
  )
}
