const STRUCTURAL_MARKER_RE = /(?:^|\s)(?:#{1,6}\s|\|\s*[^|\n]*\s*\||[-*]\s)/

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
