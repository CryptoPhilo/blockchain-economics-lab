import type { Metadata } from 'next'
import { defaultLocale, locales, type Locale } from '@/i18n/config'

type LocalizedSiteMetadata = {
  title: string
  description: string
  openGraphLocale: string
}

export const SITE_METADATA_BY_LOCALE: Record<Locale, LocalizedSiteMetadata> = {
  en: {
    title: 'BCE Lab — Blockchain Economics Research',
    description: 'Institutional-grade blockchain economic research powered by AI agents',
    openGraphLocale: 'en_US',
  },
  ko: {
    title: 'BCE Lab — 블록체인 경제 연구소',
    description: 'AI 에이전트가 구동하는 기관급 블록체인 경제 리서치',
    openGraphLocale: 'ko_KR',
  },
  fr: {
    title: 'BCE Lab — Recherche en économie blockchain',
    description: 'Recherche institutionnelle en économie blockchain propulsée par des agents IA',
    openGraphLocale: 'fr_FR',
  },
  es: {
    title: 'BCE Lab — Investigación de economía blockchain',
    description: 'Investigación institucional de economía blockchain impulsada por agentes de IA',
    openGraphLocale: 'es_ES',
  },
  de: {
    title: 'BCE Lab — Blockchain-Ökonomieforschung',
    description: 'Institutionelle Blockchain-Ökonomieforschung, unterstützt von KI-Agenten',
    openGraphLocale: 'de_DE',
  },
  ja: {
    title: 'BCE Lab — ブロックチェーン経済研究所',
    description: 'AIエージェントが支える機関投資家水準のブロックチェーン経済リサーチ',
    openGraphLocale: 'ja_JP',
  },
  zh: {
    title: 'BCE Lab — 区块链经济研究所',
    description: '由 AI 代理驱动的机构级区块链经济研究',
    openGraphLocale: 'zh_CN',
  },
}

export function normalizeSiteMetadataLocale(locale: string): Locale {
  return locales.includes(locale as Locale) ? (locale as Locale) : defaultLocale
}

export function buildLanguageAlternates() {
  return Object.fromEntries(locales.map((locale) => [locale, `/${locale}`]))
}

export function buildLocalizedSiteMetadata(locale: string): Metadata {
  const normalizedLocale = normalizeSiteMetadataLocale(locale)
  const localized = SITE_METADATA_BY_LOCALE[normalizedLocale]
  const alternateLocale = locales
    .filter((candidate) => candidate !== normalizedLocale)
    .map((candidate) => SITE_METADATA_BY_LOCALE[candidate].openGraphLocale)

  return {
    title: localized.title,
    description: localized.description,
    alternates: {
      canonical: `/${normalizedLocale}`,
      languages: buildLanguageAlternates(),
    },
    openGraph: {
      title: localized.title,
      description: localized.description,
      url: `/${normalizedLocale}`,
      siteName: 'BCE Lab',
      type: 'website',
      locale: localized.openGraphLocale,
      alternateLocale,
    },
    twitter: {
      card: 'summary_large_image',
      title: localized.title,
      description: localized.description,
    },
  }
}
