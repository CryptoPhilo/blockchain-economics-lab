import {
  SITE_METADATA_BY_LOCALE,
  buildLanguageAlternates,
  buildLocalizedSiteMetadata,
  normalizeSiteMetadataLocale,
} from './site-metadata'

describe('site metadata helpers', () => {
  it('returns localized sharing metadata for every supported locale', () => {
    for (const [locale, expected] of Object.entries(SITE_METADATA_BY_LOCALE)) {
      const metadata = buildLocalizedSiteMetadata(locale)

      expect(metadata.title).toBe(expected.title)
      expect(metadata.description).toBe(expected.description)
      expect(metadata.openGraph).toMatchObject({
        title: expected.title,
        description: expected.description,
        url: `/${locale}`,
        locale: expected.openGraphLocale,
      })
      expect(metadata.twitter).toMatchObject({
        title: expected.title,
        description: expected.description,
      })
    }
  })

  it('falls back to English metadata for unknown locale values', () => {
    expect(normalizeSiteMetadataLocale('unknown')).toBe('en')
    expect(buildLocalizedSiteMetadata('unknown').title).toBe(SITE_METADATA_BY_LOCALE.en.title)
  })

  it('exposes alternate links for all supported locale routes', () => {
    expect(buildLanguageAlternates()).toEqual({
      en: '/en',
      ko: '/ko',
      fr: '/fr',
      es: '/es',
      de: '/de',
      ja: '/ja',
      zh: '/zh',
    })
  })
})
