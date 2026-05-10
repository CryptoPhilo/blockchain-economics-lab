export type MarketingContentReport = {
  marketing_content_by_lang?: Record<string, unknown> | null
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function normalizeForComparison(value: string): string {
  return value.replace(/\s+/g, ' ').trim().toLowerCase()
}

function cleanMarketingContent(value: string): string {
  return value
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '$1')
    .replace(/\[([^\]]*?)\]\([^)]*?\)/g, '$1')
    .replace(/\s*\[\d+\]/g, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function getLocalizedMarketingContent(
  report: MarketingContentReport,
  locale: string,
  duplicateCandidate?: string | null,
): string {
  const contentByLang = report.marketing_content_by_lang
  if (!contentByLang || typeof contentByLang !== 'object') return ''

  const localeContent = contentByLang[locale]
  const fallbackContent = locale === 'en' ? contentByLang.ko : contentByLang.en
  const rawContent = isNonEmptyString(localeContent)
    ? localeContent
    : isNonEmptyString(fallbackContent)
      ? fallbackContent
      : ''

  if (!rawContent) return ''

  const cleaned = cleanMarketingContent(rawContent)
  if (!cleaned) return ''

  if (
    duplicateCandidate
    && normalizeForComparison(cleaned) === normalizeForComparison(duplicateCandidate)
  ) {
    return ''
  }

  return cleaned
}
