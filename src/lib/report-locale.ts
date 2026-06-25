import type { ProjectReport } from './types'

const ENGLISH_ASSET_FALLBACK_LOCALES = new Set(['de', 'es', 'fr'])

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

function hasLocalizedAsset(report: Partial<ProjectReport>, locale: string): boolean {
  const gdriveUrls = report.gdrive_urls_by_lang as Record<string, unknown> | undefined
  const fileUrls = report.file_urls_by_lang as Record<string, unknown> | undefined
  const slideUrls = report.slide_html_urls_by_lang as Record<string, unknown> | undefined

  return hasUrlEntry(gdriveUrls?.[locale])
    || hasUrlEntry(fileUrls?.[locale])
    || hasNonEmptyValue(slideUrls?.[locale])
}

function hasLocalizedSlideAsset(report: Partial<ProjectReport>, locale: string): boolean {
  const slideUrls = report.slide_html_urls_by_lang as Record<string, unknown> | undefined
  return hasNonEmptyValue(slideUrls?.[locale])
}

function hasActiveSummaryAuthority(report: Partial<ProjectReport>): boolean {
  const cardData = report.card_data
  if (!cardData || typeof cardData !== 'object') return false

  const summaryAuthority = (cardData as Record<string, unknown>).summary_authority
  if (!summaryAuthority || typeof summaryAuthority !== 'object') return false

  return (summaryAuthority as Record<string, unknown>).mode === 'llm_active'
}

function hasSummaryAuthorityMetadataForLocale(report: Partial<ProjectReport>, locale: string): boolean {
  if (!hasActiveSummaryAuthority(report)) return false

  const cardData = report.card_data as Record<string, unknown> | null | undefined
  const summaryByLang = cardData?.summary_by_lang as Record<string, unknown> | undefined
  const localeSummary =
    summaryByLang?.[locale]
    ?? (report as Record<string, unknown>)[`card_summary_${locale}`]
    ?? cardData?.[`summary_${locale}`]

  if (hasNonEmptyValue(localeSummary)) return true
  if (report.language === locale && hasNonEmptyValue(cardData?.summary)) return true

  if (locale !== 'en') return false

  return hasNonEmptyValue(summaryByLang?.en)
    || hasNonEmptyValue(report.card_summary_en)
    || hasNonEmptyValue(cardData?.summary_en)
    || hasNonEmptyValue(cardData?.summary)
}

export function reportHasSlideAssetForLocale(
  report: Partial<ProjectReport>,
  locale: string,
): boolean {
  if (!locale) {
    return true
  }

  if (hasLocalizedSlideAsset(report, locale)) {
    return true
  }

  return ENGLISH_ASSET_FALLBACK_LOCALES.has(locale) && hasLocalizedSlideAsset(report, 'en')
}

export function reportSupportsLocale(report: ProjectReport, locale: string): boolean {
  if (!locale) {
    return true
  }

  if (hasLocalizedAsset(report, locale)) {
    return true
  }

  if (hasSummaryAuthorityMetadataForLocale(report, locale)) {
    return true
  }

  if (ENGLISH_ASSET_FALLBACK_LOCALES.has(locale) && hasLocalizedAsset(report, 'en')) {
    return true
  }

  if (report.language) {
    return report.language === locale
  }

  return false
}

export function pickLocaleReport<T extends Pick<ProjectReport, 'language'> & Partial<ProjectReport>>(
  reports: T[],
  locale: string,
): T | undefined {
  return reports.find((report) => report.language === locale)
    || reports.find((report) => hasLocalizedAsset(report, locale))
    || reports.find((report) => hasSummaryAuthorityMetadataForLocale(report, locale))
    || (ENGLISH_ASSET_FALLBACK_LOCALES.has(locale)
      ? reports.find((report) => hasLocalizedAsset(report, 'en'))
      : undefined)
    || reports.find((report) => !report.language)
}
