export { cleanCardSummary } from '@/lib/report-summary'

export type CardDataRecord = Record<string, unknown>

export type SummaryReportRecord = Record<string, unknown> & {
  card_summary_en?: string | null
  language?: string | null
}

export type ReportDateRecord = Record<string, unknown> & {
  card_data?: CardDataRecord | null
  published_at?: string | null
  updated_at?: string | null
  created_at?: string | null
}

const SUPPORTED_SLIDE_LOCALES = new Set(['ko', 'en', 'fr', 'es', 'de', 'ja', 'zh'])
const ENGLISH_ASSET_FALLBACK_LOCALES = new Set(['de', 'es', 'fr'])

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function hasUrlEntry(value: unknown): boolean {
  if (isNonEmptyString(value)) return true

  if (!value || typeof value !== 'object') return false

  const entry = value as { url?: unknown; download_url?: unknown }
  return isNonEmptyString(entry.url) || isNonEmptyString(entry.download_url)
}

function resolveUrlEntry(value: unknown, preferDownload = false): string | null {
  if (isNonEmptyString(value)) return value

  if (!value || typeof value !== 'object') return null

  const entry = value as { url?: unknown; download_url?: unknown }
  const preferred = preferDownload ? entry.download_url : entry.url
  const fallback = preferDownload ? entry.url : entry.download_url

  if (isNonEmptyString(preferred)) return preferred
  if (isNonEmptyString(fallback)) return fallback
  return null
}

function getLocaleFromSlideUrl(url: string): string | null {
  try {
    const parsed = new URL(url)
    const pathParts = parsed.pathname.split('/').filter(Boolean)
    const filename = pathParts.at(-1) || ''
    const parent = pathParts.at(-2) || ''

    if (SUPPORTED_SLIDE_LOCALES.has(parent)) return parent

    const filenameMatch = filename.match(/(?:^|[_./-])(ko|en|fr|es|de|ja|zh)(?:\.html)?$/i)
    return filenameMatch ? filenameMatch[1].toLowerCase() : null
  } catch {
    return null
  }
}

function resolveSlideUrlForLocale(
  urlsByLang: Record<string, unknown> | null | undefined,
  locale: string,
  includeEnglishFallback: boolean,
): string | null {
  if (!urlsByLang || typeof urlsByLang !== 'object') return null

  const resolveCandidate = (candidateLocale: string): string | null => {
    const candidate = urlsByLang[candidateLocale]
    if (typeof candidate === 'string' && candidate) {
      const urlLocale = getLocaleFromSlideUrl(candidate)
      if (urlLocale && urlLocale !== candidateLocale) return null
      return candidate
    }
    return null
  }

  return resolveCandidate(locale) ?? (includeEnglishFallback ? resolveCandidate('en') : null)
}

function hasSlideAssetForLocale(
  report: {
    slide_html_urls_by_lang?: Record<string, unknown> | null
  },
  locale: string,
  includeEnglishFallback = false,
): boolean {
  return resolveSlideUrlForLocale(
    report.slide_html_urls_by_lang,
    locale,
    includeEnglishFallback,
  ) !== null
}

function hasPdfAssetForLocale(
  report: {
    gdrive_urls_by_lang?: Record<string, unknown> | null
    file_urls_by_lang?: Record<string, unknown> | null
  },
  locale: string,
  includeEnglishFallback = false,
): boolean {
  if (
    hasUrlEntry(report.gdrive_urls_by_lang?.[locale])
    || hasUrlEntry(report.file_urls_by_lang?.[locale])
  ) {
    return true
  }

  return includeEnglishFallback && (
    hasUrlEntry(report.gdrive_urls_by_lang?.en)
    || hasUrlEntry(report.file_urls_by_lang?.en)
  )
}

export function resolveSlideUrl(
  urlsByLang: Record<string, unknown> | null | undefined,
  locale: string,
): string | null {
  return resolveSlideUrlForLocale(
    urlsByLang,
    locale,
    ENGLISH_ASSET_FALLBACK_LOCALES.has(locale),
  )
}

export function resolveReportPdfUrl(
  report: {
    language?: string | null
    gdrive_url?: string | null
    gdrive_download_url?: string | null
    file_url?: string | null
    gdrive_urls_by_lang?: Record<string, unknown> | null
    file_urls_by_lang?: Record<string, unknown> | null
  } | null | undefined,
  locale: string,
  preferDownload = false,
): string | null {
  if (!report) return null

  const localeUrl =
    resolveUrlEntry(report.gdrive_urls_by_lang?.[locale], preferDownload)
    ?? resolveUrlEntry(report.file_urls_by_lang?.[locale], preferDownload)
  if (localeUrl) return localeUrl

  if (ENGLISH_ASSET_FALLBACK_LOCALES.has(locale)) {
    const englishUrl =
      resolveUrlEntry(report.gdrive_urls_by_lang?.en, preferDownload)
      ?? resolveUrlEntry(report.file_urls_by_lang?.en, preferDownload)
    if (englishUrl) return englishUrl
  }

  if (report.language === locale) {
    return (preferDownload
      ? report.gdrive_download_url || report.gdrive_url || report.file_url
      : report.gdrive_url || report.file_url || report.gdrive_download_url) || null
  }

  return null
}

export function getLocalizedSummary(
  locale: string,
  report: SummaryReportRecord,
  cardData: CardDataRecord | null,
): string {
  const summaryByLang = cardData?.summary_by_lang as Record<string, unknown> | undefined

  // Summary copy is resolved only from DB metadata, never from slide HTML/PDF
  // artifacts. Keep this order aligned with the project_reports contract:
  // summary_by_lang[locale] -> card_summary_<locale> -> card_data.summary_<locale>
  // -> same-locale generic card_data.summary -> English metadata only on /en.
  const localeSummary =
    summaryByLang?.[locale]
    ?? report[`card_summary_${locale}`]
    ?? cardData?.[`summary_${locale}`]

  if (isNonEmptyString(localeSummary)) return localeSummary

  if (report.language === locale && isNonEmptyString(cardData?.summary)) {
    return cardData.summary
  }

  if (locale !== 'en') return ''

  const englishSummary =
    summaryByLang?.en
    ?? report.card_summary_en
    ?? cardData?.summary_en
    ?? cardData?.summary

  return isNonEmptyString(englishSummary) ? englishSummary : ''
}

function getReportPolicyTimestamp(report: ReportDateRecord): string | null {
  const cardData = report.card_data
  const generatedAt = cardData?.generated_at
  if (isNonEmptyString(generatedAt)) return generatedAt
  if (isNonEmptyString(report.published_at)) return report.published_at
  if (isNonEmptyString(report.updated_at)) return report.updated_at
  if (isNonEmptyString(report.created_at)) return report.created_at
  return null
}

function isNewerDate(candidate: string, current: string): boolean {
  return new Date(candidate).getTime() > new Date(current).getTime()
}

export function getReportDisplayDate(
  reports: ReportDateRecord[] | null | undefined,
  selectedReport: ReportDateRecord | null,
): string | null {
  const selectedTimestamp = selectedReport ? getReportPolicyTimestamp(selectedReport) : null
  let newest = selectedTimestamp

  for (const report of reports ?? []) {
    const candidate = getReportPolicyTimestamp(report)
    if (!candidate) continue
    if (!newest || isNewerDate(candidate, newest)) newest = candidate
  }

  return newest
}

export type LocaleReportState<T> =
  | { status: 'not_found' }
  | { status: 'available'; report: T }
  | { status: 'locale_pending' }

export function getLocaleReportState<T extends {
  language?: string | null
  gdrive_urls_by_lang?: Record<string, unknown> | null
  file_urls_by_lang?: Record<string, unknown> | null
  slide_html_urls_by_lang?: Record<string, unknown> | null
}>(
  reports: T[] | null | undefined,
  locale: string,
): LocaleReportState<T> {
  if (!reports || reports.length === 0) {
    return { status: 'not_found' }
  }

  const localeReport = reports.find((report) => report.language === locale)
  if (localeReport) {
    return { status: 'available', report: localeReport }
  }

  const includeEnglishFallback = ENGLISH_ASSET_FALLBACK_LOCALES.has(locale)

  const localeSlideReport = reports.find((report) => (
    hasSlideAssetForLocale(report, locale, includeEnglishFallback)
  ))
  if (localeSlideReport) {
    return { status: 'available', report: localeSlideReport }
  }

  const localePdfReport = reports.find((report) => (
    hasPdfAssetForLocale(report, locale, includeEnglishFallback)
  ))
  if (localePdfReport) {
    return { status: 'available', report: localePdfReport }
  }

  return { status: 'locale_pending' }
}
