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
import { createRequire } from 'module'
import { join } from 'path'
import { pathToFileURL } from 'url'
const require = createRequire(import.meta.url)
const {
  CMC_TOP_30_EXCHANGE_SNAPSHOT_DATE,
  CMC_TOP_30_EXCHANGE_SOURCE_URL,
  CMC_TOP_30_EXCHANGES,
  findCmcTop30ExchangeReference,
} = require('../src/lib/exchange-top30') as typeof import('../src/lib/exchange-top30')

type CmcTop30ExchangeReference = import('../src/lib/exchange-top30').CmcTop30ExchangeReference

type ProjectStatus = 'active' | 'monitoring_only' | string

interface Options {
  apply: boolean
  exchanges: string[]
  cmcTop30: boolean
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
  cmcRank: number | null
  coingeckoId: string | null
  candidateCount: number
  listedProjectCount: number
  averageBceScore: number | null
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
  const options: Options = { apply: false, exchanges: [], cmcTop30: false, pageLimit: 2, pageSize: 250 }

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    const next = argv[i + 1]

    if (arg === '--apply') {
      options.apply = true
    } else if (arg === '--dry-run') {
      options.apply = false
    } else if (arg === '--cmc-top30') {
      options.cmcTop30 = true
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

  if (options.exchanges.length === 0 && !options.cmcTop30) {
    throw new Error('--exchange or --cmc-top30 is required')
  }

  return options
}

function printHelp(): void {
  console.log(`Usage: npx ts-node scripts/backfill-exchange-listings.ts --exchange binance,gdax [--dry-run|--apply]
       npx ts-node scripts/backfill-exchange-listings.ts --cmc-top30 [--dry-run|--apply]

Options:
  --exchange, --exchanges  Comma-separated CoinGecko exchange ids to backfill.
  --cmc-top30              Seed the CMC Top 30 exchange snapshot and backfill listings where CoinGecko ids are mapped.
  --dry-run                Report candidates and aggregate evidence without writes.
  --apply                  Upsert exchange rows and active listing rows.
  --page-limit             CoinGecko ticker pages per exchange. Default: 2.
  --page-size              Supabase page size. Default: 250.
`)
}

function buildExchangeScope(options: Options): CmcTop30ExchangeReference[] {
  const references = new Map<string, CmcTop30ExchangeReference>()

  if (options.cmcTop30) {
    for (const reference of CMC_TOP_30_EXCHANGES) references.set(reference.slug, reference)
  }

  for (const exchange of options.exchanges) {
    const reference = findCmcTop30ExchangeReference(exchange) ?? {
      cmcRank: 0,
      cmcName: exchange,
      slug: exchange,
      coingeckoId: exchange,
      aliases: [],
    }
    references.set(reference.slug, reference)
  }

  return Array.from(references.values())
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
  reference: CmcTop30ExchangeReference,
  candidates: ListingCandidate[],
): ExchangeEvidence {
  const scores = candidates
    .map((candidate) => {
      if (candidate.project.maturity_score == null) return null
      const score = Number(candidate.project.maturity_score)
      return Number.isFinite(score) ? score : null
    })
    .filter((score): score is number => score !== null)
  const scoreTotal = scores.reduce((total, score) => total + score, 0)

  return {
    exchangeSlug: reference.slug,
    exchangeName: reference.cmcName,
    cmcRank: reference.cmcRank || null,
    coingeckoId: reference.coingeckoId,
    candidateCount: candidates.length,
    listedProjectCount: candidates.length,
    averageBceScore: scores.length > 0 ? Number((scoreTotal / scores.length).toFixed(2)) : null,
    scoredProjectCount: scores.length,
  }
}

async function applyExchangeListings(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: any,
  reference: CmcTop30ExchangeReference,
  candidates: ListingCandidate[],
): Promise<void> {
  const isCmcSnapshotRow = reference.cmcRank > 0
  const { data: exchange, error: exchangeError } = await supabase
    .from('exchanges')
    .upsert({
      slug: reference.slug,
      name: reference.cmcName,
      status: 'active',
      source: isCmcSnapshotRow
        ? (reference.coingeckoId ? 'coinmarketcap_coingecko' : 'coinmarketcap')
        : 'coingecko',
      source_exchange_id: reference.coingeckoId,
      metadata: {
        cmc_rank: isCmcSnapshotRow ? reference.cmcRank : null,
        cmc_name: isCmcSnapshotRow ? reference.cmcName : null,
        aliases: reference.aliases,
        coingecko_id: reference.coingeckoId,
        cmc_snapshot_date: isCmcSnapshotRow ? CMC_TOP_30_EXCHANGE_SNAPSHOT_DATE : null,
        cmc_source_url: isCmcSnapshotRow ? CMC_TOP_30_EXCHANGE_SOURCE_URL : null,
        listing_source: reference.coingeckoId ? 'coingecko_exchanges_tickers' : null,
      },
      updated_at: new Date().toISOString(),
    }, { onConflict: 'slug' })
    .select('id')
    .single()

  if (exchangeError) throw new Error(`Failed to upsert exchange ${reference.slug}: ${exchangeError.message}`)

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

  if (error) throw new Error(`Failed to upsert listings for ${reference.slug}: ${error.message}`)
}

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2))
  loadEnv()
  const { url, key } = getSupabaseCredentials()
  const supabase = createClient(url, key, { auth: { persistSession: false } })

  console.log(`Mode: ${options.apply ? 'apply' : 'dry_run'}`)
  console.log(`Source: CoinGecko /exchanges/{id}/tickers`)
  const scope = buildExchangeScope(options)
  console.log(`Scope: ${scope.map((exchange) => `${exchange.slug}${exchange.coingeckoId ? `/${exchange.coingeckoId}` : '/no-coingecko-id'}`).join(', ')}`)
  console.log(`CMC Top 30 snapshot: ${CMC_TOP_30_EXCHANGE_SNAPSHOT_DATE} ${CMC_TOP_30_EXCHANGE_SOURCE_URL}`)
  console.log(`Rules: active exchange rows and active listing rows only; duplicate pairs dedupe to one exchange/project row; inactive/delisted rows are excluded by API aggregation.`)

  const projects = await fetchTrackedProjects(supabase, options.pageSize)
  console.log(`Tracked projects loaded: ${projects.length}`)

  const evidence: ExchangeEvidence[] = []

  for (const reference of scope) {
    let tickers: CoinGeckoTicker[] = []
    let exchangeName = reference.cmcName
    let candidates: ListingCandidate[] = []

    if (reference.coingeckoId) {
      try {
        const response = await fetchCoinGeckoExchange(reference.coingeckoId, options.pageLimit)
        tickers = response.tickers
        exchangeName = response.exchangeName
        candidates = buildListingCandidates(reference.slug, reference.cmcName, tickers, projects)
      } catch (error) {
        if (reference.cmcRank <= 0) throw error
        console.error(`Listing fetch skipped for ${reference.slug}: ${error instanceof Error ? error.message : String(error)}`)
      }
    }

    console.log(`\nExchange: ${reference.cmcName} (${reference.slug})`)
    console.log(`CMC rank: ${reference.cmcRank || 'not in snapshot'}`)
    console.log(`CoinGecko id: ${reference.coingeckoId ?? 'none'}`)
    if (exchangeName !== reference.cmcName) console.log(`CoinGecko name: ${exchangeName}`)
    console.log(`CoinGecko tickers scanned: ${tickers.length}`)
    console.log(`Matched unique tracked projects: ${candidates.length}`)
    for (const candidate of candidates.slice(0, 20)) {
      console.log(`- ${candidate.project.slug} ${candidate.pair ?? ''} score=${candidate.project.maturity_score ?? 'null'} match=${candidate.matchMethod}`)
    }

    if (options.apply) {
      await applyExchangeListings(supabase, reference, candidates)
      console.log(`Applied exchange row for ${reference.slug}; listing rows: ${candidates.length}`)
    }

    evidence.push(buildEvidence(reference, candidates))
  }

  console.log('\nAggregate evidence:')
  console.log(JSON.stringify(evidence, null, 2))
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
