const DEFAULT_BASE_URL = 'https://bcelab.xyz'
const DEFAULT_SCORE_PAGE_MAX_MS = 7000
const DEFAULT_SCORE_PAGE_MAX_BYTES = 650000
const DEFAULT_SCORE_PAGE_ATTEMPTS = 3

const baseUrl = normalizeBaseUrl(
  process.env.BCE_REGRESSION_BASE_URL
    || process.env.BCE_BASE_URL
    || DEFAULT_BASE_URL,
)
const maxScorePageMs = Number(process.env.BCE_SCORE_PAGE_MAX_MS || DEFAULT_SCORE_PAGE_MAX_MS)
const maxScorePageBytes = Number(
  process.env.BCE_SCORE_PAGE_MAX_BYTES || DEFAULT_SCORE_PAGE_MAX_BYTES,
)
const scorePageAttempts = Math.max(
  1,
  Number(process.env.BCE_SCORE_PAGE_ATTEMPTS || DEFAULT_SCORE_PAGE_ATTEMPTS),
)
const cacheBust = process.env.GITHUB_RUN_ID || Date.now().toString()
const failures = []

function normalizeBaseUrl(value) {
  const trimmed = value.trim().replace(/\/+$/, '')
  if (!trimmed) return DEFAULT_BASE_URL
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

function pass(label) {
  console.log(`PASS ${label}`)
}

function fail(label, detail) {
  failures.push(`${label}${detail ? `: ${detail}` : ''}`)
}

function requireCondition(condition, label, detail) {
  if (condition) pass(label)
  else fail(label, detail)
}

function appendCacheBust(path) {
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}regression_ts=${encodeURIComponent(cacheBust)}`
}

async function fetchTextOnce(path) {
  const url = `${baseUrl}${appendCacheBust(path)}`
  const startedAt = Date.now()
  const response = await fetch(url, {
    headers: {
      'cache-control': 'no-cache',
      pragma: 'no-cache',
    },
  })
  const text = await response.text()
  return {
    url,
    status: response.status,
    ok: response.ok,
    body: text,
    bytes: Buffer.byteLength(text, 'utf8'),
    ms: Date.now() - startedAt,
  }
}

async function fetchText(path, options = {}) {
  const attempts = Math.max(1, Number(options.attempts || 1))
  let best = null

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const result = await fetchTextOnce(path)
    if (
      !best
      || (result.ok && !best.ok)
      || (result.ok === best.ok && result.ms < best.ms)
    ) {
      best = result
    }

    if (result.ok && result.ms <= maxScorePageMs) break
  }

  return best
}

async function fetchJson(path) {
  const result = await fetchText(path)
  let json = null
  try {
    json = JSON.parse(result.body)
  } catch (error) {
    fail(`parse JSON ${result.url}`, error instanceof Error ? error.message : String(error))
  }
  return { ...result, json }
}

function hasCmcRankOne(html) {
  return /CoinMarketCap #1|CMC #(<!-- -->)?1/.test(html)
}

function snippetAround(html, needle, length = 5000) {
  const index = html.indexOf(needle)
  if (index < 0) return ''
  return html.slice(index, index + length)
}

function extractRows(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.projects)) return payload.projects
  if (Array.isArray(payload?.data)) return payload.data
  return []
}

const scorePage = await fetchText('/ko/score', { attempts: scorePageAttempts })
requireCondition(scorePage.ok, 'Top500 page responds successfully', `${scorePage.status} ${scorePage.url}`)
requireCondition(
  scorePage.ms <= maxScorePageMs,
  'Top500 page response stays within performance budget',
  `${scorePage.ms}ms > ${maxScorePageMs}ms`,
)
requireCondition(
  scorePage.bytes <= maxScorePageBytes,
  'Top500 page HTML stays within size budget',
  `${scorePage.bytes} bytes > ${maxScorePageBytes} bytes`,
)
const scoreBitcoinSnippet = snippetAround(scorePage.body, '>Bitcoin<')
requireCondition(scoreBitcoinSnippet.length > 0, 'Top500 page includes Bitcoin row')
requireCondition(hasCmcRankOne(scoreBitcoinSnippet), 'Top500 Bitcoin row includes CMC rank')
requireCondition(/ECON/.test(scoreBitcoinSnippet), 'Top500 Bitcoin row includes ECON badge')
requireCondition(/MAT/.test(scoreBitcoinSnippet), 'Top500 Bitcoin row includes MAT badge')

const exchangesApi = await fetchJson('/api/exchanges')
const exchanges = extractRows(exchangesApi.json)
requireCondition(exchangesApi.ok, 'Exchange list API responds successfully', `${exchangesApi.status} ${exchangesApi.url}`)
requireCondition(exchanges.length > 0, 'Exchange list API returns rows')
requireCondition(
  exchanges.every((exchange) => Number(exchange.listedProjectCount ?? exchange.listings ?? 0) > 0),
  'Exchange list excludes zero-listing exchanges',
)
requireCondition(
  !exchanges.some((exchange) => String(exchange.slug || '').toLowerCase() === 'binance-tr'),
  'Exchange list excludes Binance TR while no listing rows are matched',
)

const binanceProjectsApi = await fetchJson('/api/exchanges/binance/projects?locale=ko')
const binanceProjects = extractRows(binanceProjectsApi.json)
const bitcoinProject = binanceProjects.find((project) => project.slug === 'bitcoin')
requireCondition(
  binanceProjectsApi.ok,
  'Binance listing API responds successfully',
  `${binanceProjectsApi.status} ${binanceProjectsApi.url}`,
)
requireCondition(Boolean(bitcoinProject), 'Binance listing API includes Bitcoin')
requireCondition(
  Array.isArray(bitcoinProject?.reportTypes) && bitcoinProject.reportTypes.includes('econ'),
  'Binance Bitcoin row includes ECON report type',
)
requireCondition(
  Array.isArray(bitcoinProject?.reportTypes) && bitcoinProject.reportTypes.includes('maturity'),
  'Binance Bitcoin row includes MAT report type',
)
requireCondition(
  Number(bitcoinProject?.cmcRank ?? bitcoinProject?.rank) === 1,
  'Binance Bitcoin row keeps CMC rank 1',
)

const binancePage = await fetchText('/ko/exchanges/binance')
requireCondition(binancePage.ok, 'Binance exchange page responds successfully', `${binancePage.status} ${binancePage.url}`)
requireCondition(
  binancePage.body.includes('거래소 상장종목 목록'),
  'Binance exchange page keeps latest detail header label',
)
const binanceBitcoinSnippet = snippetAround(binancePage.body, '>Bitcoin<')
requireCondition(binanceBitcoinSnippet.length > 0, 'Binance exchange page includes Bitcoin row')
requireCondition(hasCmcRankOne(binanceBitcoinSnippet), 'Binance exchange page Bitcoin row includes CMC rank')
requireCondition(/ECON/.test(binanceBitcoinSnippet), 'Binance exchange page Bitcoin row includes ECON badge')
requireCondition(/MAT/.test(binanceBitcoinSnippet), 'Binance exchange page Bitcoin row includes MAT badge')

if (failures.length > 0) {
  console.error('\nProduction regression gates failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log(`\nProduction regression gates verified against ${baseUrl}.`)
