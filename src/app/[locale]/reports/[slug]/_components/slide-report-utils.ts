export { cleanCardSummary } from '@/lib/report-summary'

const SUPPORTED_SLIDE_LOCALES = new Set(['ko', 'en', 'fr', 'es', 'de', 'ja', 'zh'])

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
