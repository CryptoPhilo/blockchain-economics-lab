const STRUCTURAL_MARKER_RE = /(?:^|\s)(?:#{1,6}\s|\|\s*[^|\n]*\s*\||[-*]\s)/

type CardDataSummarySource = {
  summary?: unknown
  summary_en?: unknown
  summary_ko?: unknown
  summary_fr?: unknown
  summary_es?: unknown
  summary_de?: unknown
  summary_ja?: unknown
  summary_zh?: unknown
  summary_by_lang?: Record<string, unknown> | null
}

type CardSummarySource = {
  language?: string | null
  card_summary_en?: unknown
  card_summary_ko?: unknown
  card_summary_fr?: unknown
  card_summary_es?: unknown
  card_summary_de?: unknown
  card_summary_ja?: unknown
  card_summary_zh?: unknown
  card_data?: CardDataSummarySource | null
}

type LocalizedCardSummaryOptions = {
  allowEnglishFallback?: boolean
  fallback?: string | null
}

export function cleanCardSummary(raw: string | null | undefined): string {
  if (typeof raw !== 'string') return ''

  let text = raw

  const cut = text.match(STRUCTURAL_MARKER_RE)
  if (cut && cut.index !== undefined) {
    text = text.slice(0, cut.index)
  }

  text = text.replace(/\*\*(.*?)\*\*/g, '$1')
  text = text.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '$1')
  text = text.replace(/\[([^\]]*?)\]\([^)]*?\)/g, '$1')
  text = text.replace(/\s*\[\d+\]/g, '')
  text = text.replace(/\s+/g, ' ').trim()

  return text
}

function pickCleanSummary(candidates: unknown[]): string {
  for (const candidate of candidates) {
    if (typeof candidate !== 'string') continue

    const clean = cleanCardSummary(candidate)
    if (clean) return clean
  }

  return ''
}

function pickObjectValue(source: object | null | undefined, key: string): unknown {
  return source ? (source as Record<string, unknown>)[key] : undefined
}

export function getLocalizedCardSummary(
  report: CardSummarySource,
  locale: string,
  options: LocalizedCardSummaryOptions = {},
): string {
  const cardData = report.card_data
  const summaryByLang = cardData?.summary_by_lang
  const localeCandidates = [
    summaryByLang?.[locale],
    pickObjectValue(report, `card_summary_${locale}`),
    pickObjectValue(cardData, `summary_${locale}`),
    report.language === locale ? cardData?.summary : undefined,
  ]

  const fallbackCandidates = options.allowEnglishFallback || locale === 'en'
    ? [
        summaryByLang?.en,
        report.card_summary_en,
        cardData?.summary_en,
        report.language === 'en' ? cardData?.summary : undefined,
      ]
    : []

  return pickCleanSummary([
    ...localeCandidates,
    ...fallbackCandidates,
    options.fallback,
  ])
}
