export type MarketingContentReport = {
  marketing_content_by_lang?: Record<string, unknown> | null
}

const RAW_FORMAT_RE = /(?:\$\$|\\\(|\\\[|\\(?:times|frac|sqrt|sum|prod|begin|end|left|right|cdot|Delta|alpha|beta|gamma)|\{[A-Za-z0-9_+\-]+\}|`{1,3}|^\s{0,3}#{1,6}\s+|\[[^\]]+\]\([^)]+\)|<\/?[A-Za-z][^>]*>)/im
const FORMULA_FRAGMENT_RE = /(?:\b(?:round|sqrt|log|exp|min|max)\s*\(|\b[A-Za-z]{1,4}\s*[_{]?[A-Za-z0-9-]*[}]?\s*[=+\-*/^]\s*|[=+\-*/^]\s*[A-Za-z]{1,4}\s*[_{]?[A-Za-z0-9-]*[}]?|\b[A-Za-z]{1,4}\s*\{[A-Za-z0-9_+\-]+\})/i
const STRUCTURAL_FRAGMENT_RE = /(?:\|\s*[^|\n]+\s*\||(?:^|\s)[-+*]\s+\S|(?:^|\s)\d+\.\s+\S|={2,}|:{2,})/
const MAX_MARKETING_WORDS = 60
const MAX_MARKETING_CHARS = 320

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

function wordCount(value: string): number {
  return value.split(/\s+/).filter(Boolean).length
}

function isDisplaySafeMarketingContent(value: string): boolean {
  if (!value) return false
  if (value.length > MAX_MARKETING_CHARS || wordCount(value) > MAX_MARKETING_WORDS) return false
  if (RAW_FORMAT_RE.test(value) || FORMULA_FRAGMENT_RE.test(value)) return false
  if (STRUCTURAL_FRAGMENT_RE.test(value)) return false
  return true
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
  if (!isDisplaySafeMarketingContent(cleaned)) return ''

  if (
    duplicateCandidate
    && normalizeForComparison(cleaned) === normalizeForComparison(duplicateCandidate)
  ) {
    return ''
  }

  return cleaned
}
