#!/usr/bin/env node
/**
 * Backfill normalized exchange listings from CoinGecko exchange ticker data.
 *
 * Default mode is dry-run. Use --apply only through the approved remote
 * production workflow because this writes exchanges and exchange_project_listings.
 */

import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'
import { existsSync } from 'fs'
import { join } from 'path'

type ProjectStatus = 'active' | 'monitoring_only' | string

interface Options {
  apply: boolean
  exchanges: string[]
  pageLimit: number
  pageSize: number
}

interface CoinGeckoTicker {
  base?: string
  target?: string
  coin_id?: string
  target_coin_id?: string
  trade_url?: string | null
  trust_score?: string | null
  converted_volume?: Record<string, number>
}

interface CoinGeckoExchangeResponse {
  name?: string
  tickers?: CoinGeckoTicker[]
}

interface TrackedProject {
  id: string
  slug: string
  name: string
  symbol: string | null
  coingecko_id: string | null
  cmc_rank?: number | string | null
  maturity_score: number | string | null
  status: ProjectStatus
}

interface ListingCandidate {
  exchangeSlug: string
  exchangeName: string
  project: TrackedProject
  baseSymbol: string | null
  quoteSymbol: string | null
  pair: string | null
  sourceListingId: string
  tradeUrl: string | null
  trustScore: string | null
  volumeUsd: number
  matchMethod: 'coingecko_id' | 'unique_symbol'
}

interface ExchangeEvidence {
  exchangeSlug: string
  exchangeName: string
  candidateCount: number
  listedProjectCount: number
  bceExchangeScore: number | null
  bceExchangeScoreFormulaVersion: 'bce-exchange-score-v1'
  bceExchangeScoreComponents: {
    coreBceQuality: number
    rankQuality: number
    scoreCoverage: number
    longTailPenalty: number
    listedProjectCount: number
    scoredProjectCount: number
    longTailRatio: number
  }
  scoredProjectCount: number
}

const ACTIVE_PROJECT_STATUSES = new Set<ProjectStatus>(['active', 'monitoring_only'])

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function normalizeSlug(value: string): string {
  return value.trim().toLowerCase()
}

function normalizeSymbol(value: string | null | undefined): string {
  return typeof value === 'string' ? value.trim().toUpperCase() : ''
}

function parsePositiveInteger(value: string, name: string): number {
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${name} must be a positive integer`)
  }
  return parsed
}

function parseExchangeList(value: string): string[] {
  const exchanges = value
    .split(',')
    .map(normalizeSlug)
    .filter(Boolean)

  if (exchanges.length === 0) throw new Error('--exchange requires at least one exchange id')
  if (new Set(exchanges).size !== exchanges.length) throw new Error('--exchange contains duplicate ids')
  for (const exchange of exchanges) {
    if (!/^[a-z0-9][a-z0-9_-]*$/.test(exchange)) {
      throw new Error(`Invalid exchange id: ${exchange}`)
    }
  }
  return exchanges
}

function parseArgs(argv: string[]): Options {
  const options: Options = { apply: false, exchanges: [], pageLimit: 2, pageSize: 250 }

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    const next = argv[i + 1]

    if (arg === '--apply') {
      options.apply = true
    } else if (arg === '--dry-run') {
      options.apply = false
    } else if (arg === '--exchange' || arg === '--exchanges') {
      if (!next || next.startsWith('--')) throw new Error(`${arg} requires a value`)
      options.exchanges = parseExchangeList(next)
      i++
    } else if (arg.startsWith('--exchange=')) {
      options.exchanges = parseExchangeList(arg.slice('--exchange='.length))
    } else if (arg.startsWith('--exchanges=')) {
      options.exchanges = parseExchangeList(arg.slice('--exchanges='.length))
    } else if (arg === '--page-limit') {
      if (!next || next.startsWith('--')) throw new Error('--page-limit requires a value')
      options.pageLimit = parsePositiveInteger(next, '--page-limit')
      i++
    } else if (arg.startsWith('--page-limit=')) {
      options.pageLimit = parsePositiveInteger(arg.slice('--page-limit='.length), '--page-limit')
    } else if (arg === '--page-size') {
      if (!next || next.startsWith('--')) throw new Error('--page-size requires a value')
      options.pageSize = parsePositiveInteger(next, '--page-size')
      i++
    } else if (arg.startsWith('--page-size=')) {
      options.pageSize = parsePositiveInteger(arg.slice('--page-size='.length), '--page-size')
    } else if (arg === '--help' || arg === '-h') {
      printHelp()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  if (options.exchanges.length === 0) {
    throw new Error('--exchange is required')
  }

  return options
}

function toNullableNumber(value: unknown): number | null {
  if (value == null) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function roundScore(value: number) {
  return Number(value.toFixed(2))
}

function calculateEvidenceScore(candidates: ListingCandidate[]) {
  const listedProjectCount = candidates.length
  const scored = candidates
    .map((candidate) => ({
      project: candidate.project,
      score: toNullableNumber(candidate.project.maturity_score),
    }))
    .filter((row): row is { project: TrackedProject; score: number } => row.score !== null)
  const longTailCount = candidates.filter((candidate) => {
    const rank = toNullableNumber(candidate.project.cmc_rank)
    return rank === null || rank > 1000
  }).length
  const longTailRatio = listedProjectCount > 0 ? longTailCount / listedProjectCount : 0
  const weightedScore = scored.reduce((total, { project, score }) => {
    const rank = toNullableNumber(project.cmc_rank)
    const conservativeRank = rank !== null && rank > 0 ? rank : 5000
    return total + (score / Math.log2(conservativeRank + 1))
  }, 0)
  const weightTotal = scored.reduce((total, { project }) => {
    const rank = toNullableNumber(project.cmc_rank)
    const conservativeRank = rank !== null && rank > 0 ? rank : 5000
    return total + (1 / Math.log2(conservativeRank + 1))
  }, 0)
  const coreBceQuality = weightTotal > 0 ? weightedScore / weightTotal : 0
  const rankQuality = listedProjectCount > 0
    ? candidates.reduce((total, candidate) => {
      const rank = toNullableNumber(candidate.project.cmc_rank)
      if (rank === null || rank < 1 || rank > 5000) return total
      return total + clamp(100 * (1 - Math.log10(rank) / Math.log10(5000)), 0, 100)
    }, 0) / listedProjectCount
    : 0
  const scoreCoverage = listedProjectCount > 0
    ? 100 * Math.sqrt(scored.length / listedProjectCount)
    : 0
  const longTailPenalty = 15 * clamp((longTailRatio - 0.30) / 0.70, 0, 1)

  return {
    bceExchangeScore: listedProjectCount > 0
      ? roundScore(clamp((0.60 * coreBceQuality) + (0.25 * rankQuality) + (0.15 * scoreCoverage) - longTailPenalty, 0, 100))
      : null,
    bceExchangeScoreFormulaVersion: 'bce-exchange-score-v1' as const,
    bceExchangeScoreComponents: {
      coreBceQuality: roundScore(coreBceQuality),
      rankQuality: roundScore(rankQuality),
      scoreCoverage: roundScore(scoreCoverage),
      longTailPenalty: roundScore(longTailPenalty),
      listedProjectCount,
      scoredProjectCount: scored.length,
      longTailRatio: roundScore(longTailRatio),
    },
  }
}

function printHelp(): void {
  console.log(`Usage: npx ts-node scripts/backfill-exchange-listings.ts --exchange binance,gdax [--dry-run|--apply]

Options:
  --exchange, --exchanges  Comma-separated CoinGecko exchange ids to backfill.
  --dry-run                Report candidates and aggregate evidence without writes.
  --apply                  Upsert exchange rows and active listing rows.
  --page-limit             CoinGecko ticker pages per exchange. Default: 2.
  --page-size              Supabase page size. Default: 250.
`)
}

function loadEnv(): void {
  for (const envPath of [
    join(process.cwd(), '.env.local'),
    join(process.cwd(), '.env.d', 'supabase-service.env'),
  ]) {
    if (existsSync(envPath)) config({ path: envPath, override: false, quiet: true })
  }
}

function getSupabaseCredentials(): { url: string; key: string } {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) {
    throw new Error('Missing Supabase credentials')
  }
  return { url, key }
}

async function fetchCoinGeckoExchange(
  exchangeSlug: string,
  pageLimit: number,
): Promise<{ exchangeName: string; tickers: CoinGeckoTicker[] }> {
  const tickers: CoinGeckoTicker[] = []
  let exchangeName = exchangeSlug

  for (let page = 1; page <= pageLimit; page++) {
    const url = new URL(`https://api.coingecko.com/api/v3/exchanges/${exchangeSlug}/tickers`)
    url.searchParams.set('page', String(page))
    url.searchParams.set('depth', 'false')

    const headers: Record<string, string> = {
      accept: 'application/json',
      'user-agent': 'bcelab-exchange-listing-backfill',
    }
    if (process.env.COINGECKO_API_KEY) headers['x-cg-demo-api-key'] = process.env.COINGECKO_API_KEY

    const response = await fetch(url, { headers })
    if (!response.ok) {
      throw new Error(`CoinGecko ${exchangeSlug} page ${page} failed with HTTP ${response.status}`)
    }

    const payload = (await response.json()) as CoinGeckoExchangeResponse
    if (isNonEmptyString(payload.name)) exchangeName = payload.name.trim()
    const pageTickers = payload.tickers ?? []
    tickers.push(...pageTickers)
    if (pageTickers.length === 0) break
  }

  return { exchangeName, tickers }
}

async function fetchTrackedProjects(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: any,
  pageSize: number,
): Promise<TrackedProject[]> {
  const rows: TrackedProject[] = []

  for (let offset = 0; ; offset += pageSize) {
    const { data, error } = await supabase
      .from('tracked_projects')
      .select('id, slug, name, symbol, coingecko_id, maturity_score, status')
      .in('status', Array.from(ACTIVE_PROJECT_STATUSES))
      .range(offset, offset + pageSize - 1)

    if (error) throw new Error(`Failed to fetch tracked_projects: ${error.message}`)

    const batch = (data ?? []) as TrackedProject[]
    rows.push(...batch)
    if (batch.length < pageSize) break
  }

  return rows
}

async function fetchLatestCmcRanks(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: any,
  pageSize: number,
): Promise<Map<string, number>> {
  const { data: latestSnapshot, error: latestError } = await supabase
    .from('market_data_daily')
    .select('recorded_at')
    .eq('source', 'coinmarketcap')
    .gte('cmc_rank', 1)
    .lte('cmc_rank', 5000)
    .order('recorded_at', { ascending: false })
    .limit(1)
    .maybeSingle()

  if (latestError) throw new Error(`Failed to fetch latest CMC rank snapshot date: ${latestError.message}`)
  if (!latestSnapshot?.recorded_at) return new Map()

  const ranks = new Map<string, number>()

  for (let offset = 0; ; offset += pageSize) {
    const { data, error } = await supabase
      .from('market_data_daily')
      .select('slug, cmc_rank')
      .eq('recorded_at', latestSnapshot.recorded_at)
      .eq('source', 'coinmarketcap')
      .gte('cmc_rank', 1)
      .lte('cmc_rank', 5000)
      .range(offset, offset + pageSize - 1)

    if (error) throw new Error(`Failed to fetch latest CMC ranks: ${error.message}`)

    const batch = (data ?? []) as { slug: string; cmc_rank: number | string | null }[]
    for (const row of batch) {
      const rank = toNullableNumber(row.cmc_rank)
      if (row.slug && rank !== null) ranks.set(row.slug, rank)
    }
    if (batch.length < pageSize) break
  }

  return ranks
}

function applyLatestCmcRanks(projects: TrackedProject[], rankBySlug: Map<string, number>): TrackedProject[] {
  return projects.map((project) => ({
    ...project,
    cmc_rank: rankBySlug.get(project.slug) ?? project.cmc_rank ?? null,
  }))
}

export function buildListingCandidates(
  exchangeSlug: string,
  exchangeName: string,
  tickers: CoinGeckoTicker[],
  projects: TrackedProject[],
): ListingCandidate[] {
  const byCoinGeckoId = new Map<string, TrackedProject>()
  const byUniqueSymbol = new Map<string, TrackedProject | null>()

  for (const project of projects) {
    if (isNonEmptyString(project.coingecko_id)) {
      byCoinGeckoId.set(project.coingecko_id.trim().toLowerCase(), project)
    }

    const symbol = normalizeSymbol(project.symbol)
    if (!symbol) continue
    byUniqueSymbol.set(symbol, byUniqueSymbol.has(symbol) ? null : project)
  }

  const byProject = new Map<string, ListingCandidate>()

  for (const ticker of tickers) {
    const coinId = isNonEmptyString(ticker.coin_id) ? ticker.coin_id.trim().toLowerCase() : ''
    const baseSymbol = normalizeSymbol(ticker.base)
    const coinIdProject = coinId ? byCoinGeckoId.get(coinId) : undefined
    const symbolProject = !coinIdProject && baseSymbol ? byUniqueSymbol.get(baseSymbol) : undefined
    const project = coinIdProject ?? symbolProject ?? null
    if (!project || !ACTIVE_PROJECT_STATUSES.has(project.status)) continue

    const quoteSymbol = normalizeSymbol(ticker.target)
    const pair = baseSymbol && quoteSymbol ? `${baseSymbol}/${quoteSymbol}` : null
    const candidate: ListingCandidate = {
      exchangeSlug,
      exchangeName,
      project,
      baseSymbol: baseSymbol || null,
      quoteSymbol: quoteSymbol || null,
      pair,
      sourceListingId: [exchangeSlug, coinId || project.slug, pair ?? 'spot'].join(':'),
      tradeUrl: ticker.trade_url ?? null,
      trustScore: ticker.trust_score ?? null,
      volumeUsd: Number(ticker.converted_volume?.usd ?? 0) || 0,
      matchMethod: coinIdProject ? 'coingecko_id' : 'unique_symbol',
    }

    const existing = byProject.get(project.id)
    if (!existing || candidate.volumeUsd > existing.volumeUsd) {
      byProject.set(project.id, candidate)
    }
  }

  return Array.from(byProject.values()).sort((a, b) => (
    b.volumeUsd - a.volumeUsd || a.project.slug.localeCompare(b.project.slug)
  ))
}

export function buildEvidence(
  exchangeSlug: string,
  exchangeName: string,
  candidates: ListingCandidate[],
): ExchangeEvidence {
  const score = calculateEvidenceScore(candidates)

  return {
    exchangeSlug,
    exchangeName,
    candidateCount: candidates.length,
    listedProjectCount: candidates.length,
    ...score,
    scoredProjectCount: score.bceExchangeScoreComponents.scoredProjectCount,
  }
}

async function applyExchangeListings(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: any,
  exchangeSlug: string,
  exchangeName: string,
  candidates: ListingCandidate[],
): Promise<void> {
  const { data: exchange, error: exchangeError } = await supabase
    .from('exchanges')
    .upsert({
      slug: exchangeSlug,
      name: exchangeName,
      status: 'active',
      source: 'coingecko',
      source_exchange_id: exchangeSlug,
      metadata: { source: 'coingecko_exchanges_tickers' },
      updated_at: new Date().toISOString(),
    }, { onConflict: 'slug' })
    .select('id')
    .single()

  if (exchangeError) throw new Error(`Failed to upsert exchange ${exchangeSlug}: ${exchangeError.message}`)

  const exchangeId = exchange.id as string
  const observedAt = new Date().toISOString()
  const rows = candidates.map((candidate) => ({
    exchange_id: exchangeId,
    project_id: candidate.project.id,
    listing_status: 'active',
    base_symbol: candidate.baseSymbol,
    quote_symbol: candidate.quoteSymbol,
    pair: candidate.pair,
    source: 'coingecko',
    source_listing_id: candidate.sourceListingId,
    metadata: {
      trade_url: candidate.tradeUrl,
      trust_score: candidate.trustScore,
      volume_usd: candidate.volumeUsd,
      match_method: candidate.matchMethod,
      observed_at: observedAt,
    },
    updated_at: observedAt,
  }))

  if (rows.length === 0) return

  const { error } = await supabase
    .from('exchange_project_listings')
    .upsert(rows, { onConflict: 'exchange_id,project_id' })

  if (error) throw new Error(`Failed to upsert listings for ${exchangeSlug}: ${error.message}`)
}

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2))
  loadEnv()
  const { url, key } = getSupabaseCredentials()
  const supabase = createClient(url, key, { auth: { persistSession: false } })

  console.log(`Mode: ${options.apply ? 'apply' : 'dry_run'}`)
  console.log(`Source: CoinGecko /exchanges/{id}/tickers`)
  console.log(`Scope: ${options.exchanges.join(', ')}`)
  console.log(`Rules: active exchange rows and active listing rows only; duplicate pairs dedupe to one exchange/project row; inactive/delisted rows are excluded by API aggregation.`)

  const [trackedProjects, latestCmcRanks] = await Promise.all([
    fetchTrackedProjects(supabase, options.pageSize),
    fetchLatestCmcRanks(supabase, options.pageSize),
  ])
  const projects = applyLatestCmcRanks(trackedProjects, latestCmcRanks)
  console.log(`Tracked projects loaded: ${projects.length}; CMC rank snapshot rows loaded: ${latestCmcRanks.size}`)

  const evidence: ExchangeEvidence[] = []

  for (const exchangeSlug of options.exchanges) {
    const { exchangeName, tickers } = await fetchCoinGeckoExchange(exchangeSlug, options.pageLimit)
    const candidates = buildListingCandidates(exchangeSlug, exchangeName, tickers, projects)

    console.log(`\nExchange: ${exchangeName} (${exchangeSlug})`)
    console.log(`CoinGecko tickers scanned: ${tickers.length}`)
    console.log(`Matched unique tracked projects: ${candidates.length}`)
    for (const candidate of candidates.slice(0, 20)) {
      console.log(`- ${candidate.project.slug} ${candidate.pair ?? ''} score=${candidate.project.maturity_score ?? 'null'} match=${candidate.matchMethod}`)
    }

    if (options.apply) {
      await applyExchangeListings(supabase, exchangeSlug, exchangeName, candidates)
      console.log(`Applied rows for ${exchangeSlug}: ${candidates.length}`)
    }

    evidence.push(buildEvidence(exchangeSlug, exchangeName, candidates))
  }

  console.log('\nAggregate evidence:')
  console.log(JSON.stringify(evidence, null, 2))
}

if (process.env.JEST_WORKER_ID === undefined) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
