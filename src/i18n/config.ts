export const locales = ['en', 'ko', 'fr', 'es', 'de', 'ja', 'zh'] as const
export type Locale = (typeof locales)[number]
export const defaultLocale: Locale = 'en'

export const localeNames: Record<Locale, string> = {
  en: 'English',
  ko: '한국어',
  fr: 'Français',
  es: 'Español',
  de: 'Deutsch',
  ja: '日本語',
  zh: '中文',
}
