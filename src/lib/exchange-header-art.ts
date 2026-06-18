import { findCmcTop30ExchangeReference } from './exchange-top30'

export const EXCHANGES_HEADER_BACKGROUND_IMAGE = '/images/exchanges-header-bg.png'
export const EXCHANGE_DETAIL_HEADER_BASE_IMAGE = '/images/exchange-detail-header-base.png'

type ExchangeHeaderTheme = {
  accent: string
  accentSoft: string
  highlight: string
  grid: string
  pattern: 'arc' | 'columns' | 'rings' | 'ladder' | 'nodes'
}

type HeaderStyle = {
  backgroundImage: string
}

const HEADER_THEMES: ExchangeHeaderTheme[] = [
  { accent: '#22d3ee', accentSoft: '#0ea5e9', highlight: '#f8fafc', grid: '#0f172a', pattern: 'arc' },
  { accent: '#f59e0b', accentSoft: '#f97316', highlight: '#fef3c7', grid: '#1f2937', pattern: 'columns' },
  { accent: '#60a5fa', accentSoft: '#2563eb', highlight: '#dbeafe', grid: '#111827', pattern: 'rings' },
  { accent: '#34d399', accentSoft: '#14b8a6', highlight: '#ecfeff', grid: '#0b1120', pattern: 'nodes' },
  { accent: '#fb7185', accentSoft: '#f43f5e', highlight: '#ffe4e6', grid: '#111827', pattern: 'ladder' },
  { accent: '#a78bfa', accentSoft: '#6366f1', highlight: '#eef2ff', grid: '#0f172a', pattern: 'arc' },
]

const HEADER_THEME_OVERRIDES: Record<string, Partial<ExchangeHeaderTheme>> = {
  binance: { accent: '#f0b90b', accentSoft: '#f59e0b', highlight: '#fef3c7', pattern: 'rings' },
  coinbase: { accent: '#3b82f6', accentSoft: '#60a5fa', highlight: '#dbeafe', pattern: 'columns' },
  upbit: { accent: '#22d3ee', accentSoft: '#2dd4bf', highlight: '#cffafe', pattern: 'arc' },
  okx: { accent: '#93c5fd', accentSoft: '#cbd5e1', highlight: '#e2e8f0', pattern: 'ladder' },
  bybit: { accent: '#f59e0b', accentSoft: '#fbbf24', highlight: '#fef3c7', pattern: 'columns' },
  bitget: { accent: '#06b6d4', accentSoft: '#0ea5e9', highlight: '#ecfeff', pattern: 'nodes' },
  gate: { accent: '#60a5fa', accentSoft: '#38bdf8', highlight: '#dbeafe', pattern: 'arc' },
  kucoin: { accent: '#34d399', accentSoft: '#10b981', highlight: '#d1fae5', pattern: 'nodes' },
  mexc: { accent: '#14b8a6', accentSoft: '#2dd4bf', highlight: '#ccfbf1', pattern: 'rings' },
  htx: { accent: '#2563eb', accentSoft: '#1d4ed8', highlight: '#dbeafe', pattern: 'ladder' },
  'crypto-com-exchange': { accent: '#60a5fa', accentSoft: '#2563eb', highlight: '#dbeafe', pattern: 'columns' },
  bitfinex: { accent: '#22c55e', accentSoft: '#16a34a', highlight: '#dcfce7', pattern: 'arc' },
  bingx: { accent: '#38bdf8', accentSoft: '#818cf8', highlight: '#e0f2fe', pattern: 'arc' },
  kraken: { accent: '#8b5cf6', accentSoft: '#6366f1', highlight: '#ede9fe', pattern: 'rings' },
  'binance-tr': { accent: '#f59e0b', accentSoft: '#ef4444', highlight: '#fef3c7', pattern: 'columns' },
  bitmart: { accent: '#fb7185', accentSoft: '#f97316', highlight: '#ffe4e6', pattern: 'ladder' },
  lbank: { accent: '#60a5fa', accentSoft: '#34d399', highlight: '#dbeafe', pattern: 'nodes' },
  bitstamp: { accent: '#0ea5e9', accentSoft: '#38bdf8', highlight: '#e0f2fe', pattern: 'columns' },
  bithumb: { accent: '#f97316', accentSoft: '#fb7185', highlight: '#ffedd5', pattern: 'rings' },
  xt: { accent: '#a78bfa', accentSoft: '#f472b6', highlight: '#f5f3ff', pattern: 'ladder' },
  tokocrypto: { accent: '#f59e0b', accentSoft: '#fb7185', highlight: '#fef3c7', pattern: 'nodes' },
  bitflyer: { accent: '#f97316', accentSoft: '#f59e0b', highlight: '#ffedd5', pattern: 'columns' },
  'binance-us': { accent: '#f0b90b', accentSoft: '#60a5fa', highlight: '#fef3c7', pattern: 'arc' },
  gemini: { accent: '#06b6d4', accentSoft: '#3b82f6', highlight: '#cffafe', pattern: 'rings' },
  pionex: { accent: '#2dd4bf', accentSoft: '#14b8a6', highlight: '#ccfbf1', pattern: 'columns' },
  toobit: { accent: '#38bdf8', accentSoft: '#60a5fa', highlight: '#e0f2fe', pattern: 'arc' },
  ourbit: { accent: '#fb7185', accentSoft: '#f43f5e', highlight: '#ffe4e6', pattern: 'nodes' },
  kcex: { accent: '#818cf8', accentSoft: '#38bdf8', highlight: '#e0e7ff', pattern: 'ladder' },
  coinw: { accent: '#22d3ee', accentSoft: '#60a5fa', highlight: '#cffafe', pattern: 'rings' },
  deepcoin: { accent: '#34d399', accentSoft: '#22d3ee', highlight: '#d1fae5', pattern: 'arc' },
}

function normalizeKey(value: string | null | undefined): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : ''
}

function hashExchangeKey(value: string): number {
  return Array.from(value).reduce((acc, char) => ((acc * 31) + char.charCodeAt(0)) >>> 0, 7)
}

function escapeSvgText(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

function getExchangeMonogram(name: string, slug: string): string {
  const uppercaseSlug = slug.replace(/[^a-z0-9]/gi, '').toUpperCase()
  if (uppercaseSlug.length > 0 && uppercaseSlug.length <= 4) return uppercaseSlug

  const words = name
    .split(/\s+/)
    .map((word) => word.replace(/[^A-Za-z0-9]/g, ''))
    .filter(Boolean)
  const initials = words.slice(0, 2).map((word) => word[0]?.toUpperCase() ?? '').join('')
  return initials || slug.slice(0, 2).toUpperCase()
}

function getExchangeTheme(slug: string): ExchangeHeaderTheme {
  const normalized = normalizeKey(slug)
  const fallback = HEADER_THEMES[hashExchangeKey(normalized || 'exchange') % HEADER_THEMES.length]
  return {
    ...fallback,
    ...(HEADER_THEME_OVERRIDES[normalized] ?? {}),
  }
}

function buildPattern(pattern: ExchangeHeaderTheme['pattern'], accent: string, accentSoft: string): string {
  switch (pattern) {
    case 'columns':
      return `
        <g opacity="0.54">
          <rect x="1085" y="282" width="18" height="86" rx="9" fill="${accentSoft}" />
          <rect x="1117" y="248" width="18" height="120" rx="9" fill="${accent}" />
          <rect x="1149" y="216" width="18" height="152" rx="9" fill="${accentSoft}" />
          <rect x="1181" y="182" width="18" height="186" rx="9" fill="${accent}" />
          <rect x="1213" y="232" width="18" height="136" rx="9" fill="${accentSoft}" />
          <rect x="1245" y="268" width="18" height="100" rx="9" fill="${accent}" />
        </g>`
    case 'rings':
      return `
        <g opacity="0.58" stroke="${accent}" fill="none">
          <circle cx="1180" cy="240" r="78" stroke-width="3" />
          <circle cx="1180" cy="240" r="114" stroke-width="1.5" stroke-dasharray="8 10" />
          <circle cx="1180" cy="240" r="146" stroke-width="1.2" opacity="0.55" />
        </g>`
    case 'ladder':
      return `
        <g opacity="0.52">
          <path d="M1086 326H1262" stroke="${accentSoft}" stroke-width="1.4" stroke-dasharray="6 8" />
          <path d="M1108 296H1284" stroke="${accent}" stroke-width="1.4" stroke-dasharray="6 8" />
          <path d="M1134 266H1310" stroke="${accentSoft}" stroke-width="1.4" stroke-dasharray="6 8" />
          <path d="M1162 236H1338" stroke="${accent}" stroke-width="1.4" stroke-dasharray="6 8" />
          <path d="M1192 206H1368" stroke="${accentSoft}" stroke-width="1.4" stroke-dasharray="6 8" />
        </g>`
    case 'nodes':
      return `
        <g opacity="0.56" stroke="${accentSoft}" fill="${accent}">
          <path d="M1088 316L1158 246L1230 288L1306 212" stroke-width="2.2" fill="none" />
          <circle cx="1088" cy="316" r="8" />
          <circle cx="1158" cy="246" r="8" />
          <circle cx="1230" cy="288" r="8" />
          <circle cx="1306" cy="212" r="8" />
        </g>`
    case 'arc':
    default:
      return `
        <g opacity="0.62" fill="none">
          <path d="M1022 378C1118 290 1238 206 1382 158" stroke="${accentSoft}" stroke-width="2.2" />
          <path d="M1048 410C1164 320 1288 252 1410 224" stroke="${accent}" stroke-width="1.6" stroke-dasharray="7 8" />
          <path d="M1082 436C1198 362 1302 322 1408 300" stroke="${accentSoft}" stroke-width="1.2" opacity="0.72" />
        </g>`
  }
}

function buildExchangeOverlay(slug: string, name: string): string {
  const reference = findCmcTop30ExchangeReference(slug) ?? findCmcTop30ExchangeReference(name)
  const canonicalSlug = reference?.slug ?? slug
  const theme = getExchangeTheme(canonicalSlug)
  const monogram = escapeSvgText(getExchangeMonogram(name, canonicalSlug))
  const rankLabel = reference?.cmcRank ? `TOP ${reference.cmcRank}` : 'LISTED'

  const svg = `
    <svg width="1600" height="460" viewBox="0 0 1600 460" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="panelGradient" x1="1000" y1="84" x2="1410" y2="412" gradientUnits="userSpaceOnUse">
          <stop stop-color="${theme.accent}" stop-opacity="0.28" />
          <stop offset="1" stop-color="#020617" stop-opacity="0.06" />
        </linearGradient>
        <radialGradient id="ringGlow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(1180 230) rotate(90) scale(152)">
          <stop stop-color="${theme.accent}" stop-opacity="0.34" />
          <stop offset="1" stop-color="${theme.accentSoft}" stop-opacity="0" />
        </radialGradient>
      </defs>
      <rect x="0" y="0" width="1600" height="460" fill="transparent"/>
      <rect x="968" y="56" width="498" height="348" rx="34" fill="url(#panelGradient)" stroke="${theme.accentSoft}" stroke-opacity="0.28"/>
      <rect x="1002" y="92" width="430" height="280" rx="26" stroke="${theme.grid}" stroke-opacity="0.62"/>
      <path d="M1002 156H1432" stroke="${theme.grid}" stroke-opacity="0.54"/>
      <path d="M1002 228H1432" stroke="${theme.grid}" stroke-opacity="0.54"/>
      <path d="M1002 300H1432" stroke="${theme.grid}" stroke-opacity="0.54"/>
      <path d="M1096 92V372" stroke="${theme.grid}" stroke-opacity="0.5"/>
      <path d="M1190 92V372" stroke="${theme.grid}" stroke-opacity="0.5"/>
      <path d="M1284 92V372" stroke="${theme.grid}" stroke-opacity="0.5"/>
      <path d="M1378 92V372" stroke="${theme.grid}" stroke-opacity="0.5"/>
      <circle cx="1180" cy="230" r="154" fill="url(#ringGlow)" />
      ${buildPattern(theme.pattern, theme.accent, theme.accentSoft)}
      <g opacity="0.9">
        <circle cx="1180" cy="230" r="92" fill="#020617" fill-opacity="0.72" stroke="${theme.accent}" stroke-width="2.6"/>
        <circle cx="1180" cy="230" r="70" fill="${theme.accentSoft}" fill-opacity="0.18" stroke="${theme.highlight}" stroke-opacity="0.36"/>
        <text x="1180" y="248" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="50" font-weight="700" fill="${theme.highlight}">${monogram}</text>
        <text x="1180" y="196" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="12" font-weight="600" letter-spacing="4" fill="${theme.accent}">${rankLabel}</text>
      </g>
      <g opacity="0.44">
        <path d="M1082 132C1138 112 1192 118 1250 106C1292 98 1342 76 1404 74" stroke="${theme.accent}" stroke-width="2.2" stroke-linecap="round"/>
        <path d="M1086 348C1134 318 1178 326 1228 304C1286 278 1332 286 1398 256" stroke="${theme.accentSoft}" stroke-width="2" stroke-linecap="round" stroke-dasharray="8 7"/>
      </g>
      <g opacity="0.62" fill="${theme.highlight}">
        <circle cx="1002" cy="94" r="3.5" />
        <circle cx="1020" cy="94" r="3.5" />
        <circle cx="1038" cy="94" r="3.5" />
      </g>
    </svg>
  `

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

export function getExchangesHeaderStyle(): HeaderStyle {
  return {
    backgroundImage: `linear-gradient(180deg, rgba(2, 6, 23, 0.38), rgba(2, 6, 23, 0.84)), url(${EXCHANGES_HEADER_BACKGROUND_IMAGE})`,
  }
}

export function getExchangeDetailHeaderStyle(exchange: { slug: string; name: string }): HeaderStyle {
  const overlay = buildExchangeOverlay(exchange.slug, exchange.name)
  return {
    backgroundImage: `linear-gradient(115deg, rgba(2, 6, 23, 0.88) 8%, rgba(2, 6, 23, 0.58) 48%, rgba(2, 6, 23, 0.82) 100%), url('${overlay}'), url(${EXCHANGE_DETAIL_HEADER_BASE_IMAGE})`,
  }
}
