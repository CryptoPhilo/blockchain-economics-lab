export { cleanCardSummary } from '@/lib/report-summary'

export type CardDataRecord = Record<string, unknown>

export type SummaryReportRecord = Record<string, unknown> & {
  card_summary_en?: string | null
  language?: string | null
}

const SUPPORTED_SLIDE_LOCALES = new Set(['ko', 'en', 'fr', 'es', 'de', 'ja', 'zh'])

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
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

export function resolveSlideUrl(
  urlsByLang: Record<string, unknown> | null | undefined,
  locale: string,
): string | null {
  if (!urlsByLang || typeof urlsByLang !== 'object') return null
  const candidate = urlsByLang[locale]
  if (typeof candidate === 'string' && candidate) {
    const urlLocale = getLocaleFromSlideUrl(candidate)
    if (urlLocale && urlLocale !== locale) return null
    return candidate
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
  // -> same-locale generic card_data.summary -> English fallback only on /en.
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

export type LocaleReportState<T> =
  | { status: 'not_found' }
  | { status: 'available'; report: T }
  | { status: 'locale_pending' }

export function getLocaleReportState<T extends {
  language?: string | null
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

  const slideReport = reports.find((report) => (
    resolveSlideUrl(report.slide_html_urls_by_lang, locale) !== null
  ))
  if (slideReport) {
    return { status: 'available', report: slideReport }
  }

  return { status: 'locale_pending' }
}
