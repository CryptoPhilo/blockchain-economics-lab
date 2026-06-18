const STRUCTURAL_MARKER_RE = /(?:^|\s)(?:#{1,6}\s|\|\s*[^|\n]*\s*\||[-*]\s)/
const LEADING_SECTION_TITLE_RE = /^\s*(?:#{1,6}\s*)?(?:\d+(?:\.\d+)*\.?\s*)?개요\s*및\s*개념\s*정의(?:\s*\([^)]*\))?\s*/i
const TRUNCATED_LEADING_SECTION_TITLE_RE = /^\s*(?:및\s*)?개념\s*정의\s+(?=본\s*보고서는)/
const METHODOLOGY_LEAD_IN_RE = /^본\s*보고서는\s*['"][^'"]+['"](?:과|와)\s*['"][^'"]+['"]에\s*의거하여\s*/
const SENTENCE_FINAL_CITATION_RE = /([.!?。！？][)"'\]}”’»」』]*)\s*(?:\d{1,3}|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)(?=(?:\s|$|[.!?。！？]))/g
const KOREAN_PRE_PUNCTUATION_CITATION_RE = /([다요함됨임음])(?:\d{1,3}|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)([.!?。！？])/g

export function cleanCardSummary(raw: string | null | undefined): string {
  if (typeof raw !== 'string') return ''

  let text = raw
  let previous = ''

  while (text !== previous) {
    previous = text
    text = text.replace(LEADING_SECTION_TITLE_RE, '')
    text = text.replace(TRUNCATED_LEADING_SECTION_TITLE_RE, '')
    text = text.replace(METHODOLOGY_LEAD_IN_RE, '')
  }

  const cut = text.match(STRUCTURAL_MARKER_RE)
  if (cut && cut.index !== undefined) {
    text = text.slice(0, cut.index)
  }

  text = text.replace(/\*\*(.*?)\*\*/g, '$1')
  text = text.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '$1')
  text = text.replace(/\[([^\]]*?)\]\([^)]*?\)/g, '$1')
  text = text.replace(/\s*\[\d+\]/g, '')
  text = text.replace(SENTENCE_FINAL_CITATION_RE, '$1')
  text = text.replace(KOREAN_PRE_PUNCTUATION_CITATION_RE, '$1$2')
  text = text.replace(/\s+/g, ' ').trim()

  return text
}

type SummaryCarrier = {
  language?: string | null
  card_data?: {
    summary?: unknown
    summary_en?: unknown
    summary_ko?: unknown
    summary_fr?: unknown
    summary_es?: unknown
    summary_de?: unknown
    summary_ja?: unknown
    summary_zh?: unknown
    summary_by_lang?: Record<string, unknown> | null
  } | null
  card_summary_en?: string | null
  card_summary_ko?: string | null
  card_summary_fr?: string | null
  card_summary_es?: string | null
  card_summary_de?: string | null
  card_summary_ja?: string | null
  card_summary_zh?: string | null
}

function pickString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

export function getLocalizedCardSummary(
  report: SummaryCarrier,
  locale: string,
  options: { allowEnglishFallback?: boolean } = {},
): string {
  const cardData = report.card_data && typeof report.card_data === 'object'
    ? report.card_data
    : null
  const summaryByLang = cardData?.summary_by_lang && typeof cardData.summary_by_lang === 'object'
    ? cardData.summary_by_lang
    : null

  const localized =
    pickString(summaryByLang?.[locale])
    ?? pickString(report[`card_summary_${locale}` as keyof SummaryCarrier])
    ?? pickString(cardData?.[`summary_${locale}` as keyof NonNullable<SummaryCarrier['card_data']>])

  if (localized) return cleanCardSummary(localized)

  if (report.language === locale) {
    const sameLocaleGeneric = pickString(cardData?.summary)
    if (sameLocaleGeneric) return cleanCardSummary(sameLocaleGeneric)
  }

  if (locale !== 'en' && !options.allowEnglishFallback) return ''

  const english =
    pickString(summaryByLang?.en)
    ?? pickString(report.card_summary_en)
    ?? pickString(cardData?.summary_en)
    ?? pickString(cardData?.summary)

  return cleanCardSummary(english)
}
