import type { ProjectReport, SupportedLanguage, GDriveUrlEntry } from '../types'

/**
 * Locale mapping for Intl date formatting
 */
const LOCALE_MAP: Record<SupportedLanguage, string> = {
  en: 'en-US',
  ko: 'ko-KR',
  ja: 'ja-JP',
  zh: 'zh-CN',
  fr: 'fr-FR',
  es: 'es-ES',
  de: 'de-DE',
}

/**
 * Language names for display
 */
export const LANGUAGE_NAMES: Record<SupportedLanguage, string> = {
  en: 'English',
  ko: '한국어',
  ja: '日本語',
  zh: '中文',
  fr: 'Français',
  es: 'Español',
  de: 'Deutsch',
}

/**
 * Get localized title from report
 */
export function getLocalizedTitle(
  report: ProjectReport,
  locale: SupportedLanguage
): string {
  const titleKey = `title_${locale}` as keyof ProjectReport
  const titleValue = report[titleKey]

  if (typeof titleValue === 'string' && titleValue) {
    return titleValue
  }

  if (report.title_en) {
    return report.title_en
  }

  // Fallback: generate from project data
  if (report.project) {
    const typeName = locale === 'ko' ? '포렌식 분석' : 'Forensic Analysis'
    const name = report.project.name || report.project.symbol || ''
    return name ? `${name} ${typeName} v${report.version}` : `${typeName} v${report.version}`
  }

  return `Report v${report.version}`
}

/**
 * Get localized summary from report with card_data fallback
 */
export function getLocalizedSummary(
  report: ProjectReport,
  locale: SupportedLanguage
): string {
  // Try card_summary_{locale}
  const summaryKey = `card_summary_${locale}` as keyof ProjectReport
  const summaryValue = report[summaryKey]

  if (typeof summaryValue === 'string' && summaryValue) {
    return summaryValue
  }

  // Fallback to English
  if (report.card_summary_en) {
    return report.card_summary_en
  }

  // Fallback to card_data.summary
  if (report.card_data?.summary) {
    return report.card_data.summary
  }

  return ''
}

/**
 * Get localized keywords from report with card_data fallback
 */
export function getLocalizedKeywords(
  report: ProjectReport,
  locale: SupportedLanguage
): string[] {
  const cardData = report.card_data

  // Try keywords_{locale} from card_data
  if (cardData) {
    const keywordsKey = `keywords_${locale}` as keyof typeof cardData
    const keywordsValue = cardData[keywordsKey]

    if (Array.isArray(keywordsValue) && keywordsValue.length > 0) {
      return keywordsValue
    }
  }

  // Try card_keywords field (typically Korean for legacy data)
  if (locale === 'ko' && Array.isArray(report.card_keywords) && report.card_keywords.length > 0) {
    return report.card_keywords
  }

  // Fallback to English keywords
  if (cardData?.keywords_en && Array.isArray(cardData.keywords_en)) {
    return cardData.keywords_en
  }

  // Fallback to generic keywords
  if (Array.isArray(report.card_keywords)) {
    return report.card_keywords
  }

  if (cardData?.keywords && Array.isArray(cardData.keywords)) {
    return cardData.keywords
  }

  return []
}

/**
 * Resolve URL from GDrive entry
 */
function resolveGDriveUrl(val: unknown, preferDownload = false): string | undefined {
  if (typeof val === 'string') {
    return val
  }

  if (val && typeof val === 'object' && 'url' in val) {
    const entry = val as GDriveUrlEntry
    return preferDownload ? (entry.download_url || entry.url) : entry.url
  }

  return undefined
}

/**
 * Get report file URL with language fallback
 */
export function getReportFileUrl(
  report: ProjectReport,
  locale: SupportedLanguage,
  preferDownload = false
): string | null {
  const gdriveByLang = (report.gdrive_urls_by_lang || {}) as Record<string, unknown>
  const filesByLang = (report.file_urls_by_lang || {}) as Record<string, string>

  // Try requested language
  let fileUrl: string | null = resolveGDriveUrl(gdriveByLang[locale], preferDownload) || filesByLang[locale] || null

  // Fallback to English
  if (!fileUrl && locale !== 'en') {
    fileUrl = resolveGDriveUrl(gdriveByLang['en'], preferDownload) || filesByLang['en'] || null
  }

  // Fallback to report-level URLs
  if (!fileUrl) {
    fileUrl = preferDownload
      ? (report.gdrive_download_url || report.gdrive_url || report.file_url || null)
      : (report.gdrive_url || report.file_url || null)
  }

  return fileUrl
}

/**
 * Get all available language versions of a report
 */
export function getAvailableLanguages(report: ProjectReport): SupportedLanguage[] {
  const gdriveByLang = (report.gdrive_urls_by_lang || {}) as Record<string, unknown>
  const filesByLang = (report.file_urls_by_lang || {}) as Record<string, string>

  const languages = new Set<SupportedLanguage>()

  // Add languages from gdrive_urls_by_lang
  Object.keys(gdriveByLang).forEach(lang => {
    if (resolveGDriveUrl(gdriveByLang[lang])) {
      languages.add(lang as SupportedLanguage)
    }
  })

  // Add languages from file_urls_by_lang
  Object.keys(filesByLang).forEach(lang => {
    if (filesByLang[lang]) {
      languages.add(lang as SupportedLanguage)
    }
  })

  return Array.from(languages)
}

/**
 * Get risk score from report with card_data fallback
 */
export function getRiskScore(report: ProjectReport): number {
  return report.card_risk_score ?? report.card_data?.risk_score ?? 0
}

/**
 * Get risk level from report with card_data fallback
 */
export function getRiskLevel(report: ProjectReport): string {
  return (report.risk_level || report.card_data?.risk_level || 'elevated').toLowerCase()
}

/**
 * Get price change data from report
 */
export function getPriceChange(report: ProjectReport): {
  change24h: number
  direction: 'up' | 'down'
} {
  const cardData = report.card_data
  const change24h = cardData?.price_change_24h ?? cardData?.change_24h ?? 0
  const direction = cardData?.direction ?? (change24h >= 0 ? 'up' : 'down')

  return { change24h, direction }
}

/**
 * Format date using locale-aware formatting
 */
export function formatReportDate(
  dateStr: string | null | undefined,
  locale: SupportedLanguage,
  options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }
): string {
  if (!dateStr) {
    return '—'
  }

  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString(LOCALE_MAP[locale] || 'en-US', options)
  } catch {
    return '—'
  }
}

/**
 * Format relative time (e.g., "2h ago", "3일 전")
 */
export function formatRelativeTime(
  dateStr: string,
  locale: SupportedLanguage
): string {
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now.getTime() - date.getTime()
  const diffMinutes = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))

  if (diffMinutes < 60) {
    return locale === 'ko' ? `${diffMinutes}분 전` : `${diffMinutes}m ago`
  }

  if (diffHours < 24) {
    return locale === 'ko' ? `${diffHours}시간 전` : `${diffHours}h ago`
  }

  const diffDays = Math.floor(diffHours / 24)
  return locale === 'ko' ? `${diffDays}일 전` : `${diffDays}d ago`
}

/**
 * Check whether a date falls within the given number of hours from now.
 */
export function isWithinHours(
  dateStr: string | null | undefined,
  hours: number,
  now = new Date()
): boolean {
  if (!dateStr || hours < 0) {
    return false
  }

  const date = new Date(dateStr)
  const dateMs = date.getTime()
  const nowMs = now.getTime()
  const maxAgeMs = hours * 60 * 60 * 1000

  if (!Number.isFinite(dateMs) || !Number.isFinite(nowMs)) {
    return false
  }

  const diffMs = nowMs - dateMs

  if (diffMs < 0) {
    return false
  }

  return diffMs <= maxAgeMs
}

/**
 * Get generated/published date for report
 */
export function getReportGeneratedDate(report: ProjectReport): string | null {
  return report.card_data?.generated_at || report.published_at || report.created_at || null
}

/**
 * Simple date formatting for reports list (English-only)
 */
export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
