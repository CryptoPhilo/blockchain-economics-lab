import type { ProjectReport } from './types'

type TranslationState = 'completed' | 'published'

const COMPLETED_TRANSLATION_STATES = new Set<TranslationState>(['completed', 'published'])

function hasNonEmptyValue(value: unknown): boolean {
  if (typeof value === 'string') {
    return value.trim().length > 0
  }

  if (Array.isArray(value)) {
    return value.some(hasNonEmptyValue)
  }

  return false
}

function hasUrlEntry(value: unknown): boolean {
  if (typeof value === 'string') {
    return value.trim().length > 0
  }

  if (!value || typeof value !== 'object') {
    return false
  }

  const entry = value as { url?: unknown; download_url?: unknown }
  return hasNonEmptyValue(entry.url) || hasNonEmptyValue(entry.download_url)
}

function hasLocalizedAsset(report: ProjectReport, locale: string): boolean {
  const gdriveUrls = report.gdrive_urls_by_lang as Record<string, unknown> | undefined
  const fileUrls = report.file_urls_by_lang as Record<string, unknown> | undefined
  const slideUrls = report.slide_html_urls_by_lang as Record<string, unknown> | undefined

  return hasUrlEntry(gdriveUrls?.[locale])
    || hasUrlEntry(fileUrls?.[locale])
    || hasNonEmptyValue(slideUrls?.[locale])
}

function hasCompletedTranslation(report: ProjectReport, locale: string): boolean {
  const translationStatus = report.translation_status as Record<string, unknown> | undefined
  const status = translationStatus?.[locale]

  return typeof status === 'string' && COMPLETED_TRANSLATION_STATES.has(status as TranslationState)
}

export function reportSupportsLocale(report: ProjectReport, locale: string): boolean {
  if (!locale) {
    return true
  }

  if (report.language) {
    return report.language === locale
  }

  return hasLocalizedAsset(report, locale)
    || hasCompletedTranslation(report, locale)
}

export function pickLocaleReport<T extends Pick<ProjectReport, 'language'>>(reports: T[], locale: string): T | undefined {
  return reports.find((report) => report.language === locale)
    || reports.find((report) => !report.language)
}
