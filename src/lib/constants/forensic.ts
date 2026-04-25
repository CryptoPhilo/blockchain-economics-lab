/**
 * Forensic report configuration constants
 * Centralized risk levels, colors, and multilingual labels
 */

export const RISK_CONFIG = {
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
  moderate: {
    accent: 'from-yellow-600 to-orange-700',
    badge: 'bg-yellow-500 text-white',
    glow: 'shadow-yellow-800/20',
    stroke: '#D97706',
  },
} as const

export type RiskLevel = keyof typeof RISK_CONFIG

export const FORENSIC_LABELS = {
  viewReport: {
    ko: '전체 보고서 보기 →',
    en: 'View Full Report →',
    ja: '完全レポートを見る →',
    zh: '查看完整报告 →',
    fr: 'Voir le rapport complet →',
    es: 'Ver informe completo →',
    de: 'Vollständigen Bericht ansehen →',
  },
  riskScore: {
    ko: '위험 점수',
    en: 'Risk Score',
    ja: 'リスクスコア',
    zh: '风险评分',
    fr: 'Score de risque',
    es: 'Puntuación de riesgo',
    de: 'Risikobewertung',
  },
  riskLevel: {
    critical: {
      ko: '심각 위험',
      en: 'Critical Risk',
      ja: '重大リスク',
      zh: '严重风险',
      fr: 'Risque critique',
      es: 'Riesgo crítico',
      de: 'Kritisches Risiko',
    },
    high: {
      ko: '높음 위험',
      en: 'High Risk',
      ja: '高リスク',
      zh: '高风险',
      fr: 'Risque élevé',
      es: 'Riesgo alto',
      de: 'Hohes Risiko',
    },
    elevated: {
      ko: '경계 위험',
      en: 'Elevated Risk',
      ja: '警戒リスク',
      zh: '警戒风险',
      fr: 'Risque modéré',
      es: 'Riesgo moderado',
      de: 'Erhöhtes Risiko',
    },
    moderate: {
      ko: '보통 위험',
      en: 'Moderate Risk',
      ja: '中程度リスク',
      zh: '中等风险',
      fr: 'Risque modéré',
      es: 'Riesgo moderado',
      de: 'Mäßiges Risiko',
    },
  },
  defaultSummary: {
    ko: '포렌식 분석 진행 중...',
    en: 'Forensic analysis in progress...',
    ja: 'フォレンジック分析進行中...',
    zh: '取证分析进行中...',
    fr: 'Analyse forensique en cours...',
    es: 'Análisis forense en curso...',
    de: 'Forensische Analyse läuft...',
  },
} as const

export const FORENSIC_LIST_CONFIG = {
  color: 'bg-red-500/20 text-red-400 border-red-500/30',
  label: 'FOR',
  icon: '🔍',
} as const

export function getLabel(
  labels: Record<string, string>,
  locale: string,
  fallback = 'en'
): string {
  return labels[locale] || labels[fallback] || Object.values(labels)[0] || ''
}
