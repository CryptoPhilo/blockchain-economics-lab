#!/usr/bin/env node
/**
 * Backfill products.cover_image_url from published report slide HTML covers.
 *
 * Default mode is dry-run. Use --apply only in the approved remote execution
 * path because this updates production products rows.
 */

import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'
import { existsSync } from 'fs'
import { join } from 'path'

type ReportType = 'econ' | 'maturity' | 'forensic'
type JsonMap = Record<string, unknown>

interface ReportRow {
  id: string
  project_id: string
  product_id: string | null
  report_type: ReportType
  language: string | null
  status: string | null
  published_at: string | null
  updated_at: string | null
  created_at: string | null
  slide_html_urls_by_lang: unknown
  tracked_projects?: {
    id: string
    name: string
    slug: string
  } | null
  products?: {
    id: string
    cover_image_url: string | null
  } | null
}

interface CoverCandidate {
  reportId: string
  productId: string
  projectSlug: string
  projectName: string
  reportType: ReportType
  language: string
  htmlUrl: string
  storagePath: string
  coverStoragePath: string
  coverPublicUrl: string
  oldCoverUrl: string | null
  publishedAt: string | null
}

interface Options {
  apply: boolean
  pageSize: number
  slug?: string
  reportType?: ReportType
}

const STORAGE_TYPE_BY_REPORT_TYPE: Record<ReportType, string> = {
  econ: 'econ',
  maturity: 'mat',
  forensic: 'for',
}

const IMAGE_MIME_TO_EXTENSION: Record<string, string> = {
  'image/jpeg': 'jpg',
  'image/jpg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
}

function isPlainObject(value: unknown): value is JsonMap {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function parseReportType(value: string): ReportType {
  if (value === 'econ' || value === 'maturity' || value === 'forensic') return value
  throw new Error('--type must be econ, maturity, or forensic')
}

function parseArgs(argv: string[]): Options {
  const options: Options = { apply: false, pageSize: 1000 }
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    const next = argv[i + 1]
    if (arg === '--apply') {
      options.apply = true
    } else if (arg === '--dry-run') {
      options.apply = false
    } else if (arg === '--slug') {
      if (!next || next.startsWith('--')) throw new Error('--slug requires a value')
      options.slug = next
      i++
    } else if (arg.startsWith('--slug=')) {
      options.slug = arg.slice('--slug='.length)
    } else if (arg === '--type' || arg === '--report-type') {
      if (!next || next.startsWith('--')) throw new Error(`${arg} requires a value`)
      options.reportType = parseReportType(next)
      i++
    } else if (arg.startsWith('--type=')) {
      options.reportType = parseReportType(arg.slice('--type='.length))
    } else if (arg.startsWith('--report-type=')) {
      options.reportType = parseReportType(arg.slice('--report-type='.length))
    } else if (arg === '--page-size') {
      if (!next || next.startsWith('--')) throw new Error('--page-size requires a value')
      options.pageSize = Number(next)
      i++
    } else if (arg.startsWith('--page-size=')) {
      options.pageSize = Number(arg.slice('--page-size='.length))
    } else if (arg === '--help' || arg === '-h') {
      printHelp()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }
  if (!Number.isInteger(options.pageSize) || options.pageSize <= 0) {
    throw new Error('--page-size must be a positive integer')
  }
  return options
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
    console.error('Missing Supabase credentials.')
    process.exit(1)
  }
  return { url, key }
}

function publicUrlForStoragePath(supabaseUrl: string, path: string): string {
  return `${supabaseUrl.replace(/\/$/, '')}/storage/v1/object/public/slides/${path}`
}

export function getPreferredReportLanguage(report: ReportRow): string | null {
  if (isNonEmptyString(report.language)) return report.language.trim()
  const urls = isPlainObject(report.slide_html_urls_by_lang) ? report.slide_html_urls_by_lang : {}
  const langs = Object.keys(urls).filter(lang => isNonEmptyString(urls[lang])).sort()
  return langs[0] ?? null
}

export function getSlideHtmlUrl(report: ReportRow, language: string): string | null {
  const urls = isPlainObject(report.slide_html_urls_by_lang) ? report.slide_html_urls_by_lang : {}
  const localized = urls[language]
  if (isNonEmptyString(localized)) return localized.trim()
  const first = Object.values(urls).find(isNonEmptyString)
  return first?.trim() ?? null
}

export function storagePathFromPublicSlidesUrl(url: string): string | null {
  const marker = '/storage/v1/object/public/slides/'
  const index = url.indexOf(marker)
  if (index < 0) return null
  return decodeURIComponent(url.slice(index + marker.length).split('?')[0])
}

export function extractFirstEmbeddedImage(html: string): { mimeType: string; bytes: Buffer; extension: string } | null {
  const match = html.match(/data:(image\/(?:jpeg|jpg|png|webp));base64,([A-Za-z0-9+/=]+)/)
  if (!match) return null
  const mimeType = match[1].toLowerCase()
  const extension = IMAGE_MIME_TO_EXTENSION[mimeType]
  if (!extension) return null
  return {
    mimeType,
    bytes: Buffer.from(match[2], 'base64'),
    extension,
  }
}

export function buildReportCoverCandidates(
  reports: ReportRow[],
  supabaseUrl: string,
): CoverCandidate[] {
  const candidates: CoverCandidate[] = []
  for (const report of reports) {
    if (!report.product_id) continue
    const product = report.products
    if (isNonEmptyString(product?.cover_image_url)) continue
    const project = report.tracked_projects
    if (!project?.slug) continue
    const language = getPreferredReportLanguage(report)
    if (!language) continue
    const htmlUrl = getSlideHtmlUrl(report, language)
    if (!htmlUrl) continue
    const storagePath = storagePathFromPublicSlidesUrl(htmlUrl)
    if (!storagePath) continue

    const storageType = STORAGE_TYPE_BY_REPORT_TYPE[report.report_type]
    const coverStoragePath = `${storageType}/${project.slug}/latest/${language}-cover.jpg`
    candidates.push({
      reportId: report.id,
      productId: report.product_id,
      projectSlug: project.slug,
      projectName: project.name,
      reportType: report.report_type,
      language,
      htmlUrl,
      storagePath,
      coverStoragePath,
      coverPublicUrl: publicUrlForStoragePath(supabaseUrl, coverStoragePath),
      oldCoverUrl: product?.cover_image_url ?? null,
      publishedAt: report.published_at || report.updated_at || report.created_at,
    })
  }
  return candidates.sort((a, b) => (
    a.projectSlug.localeCompare(b.projectSlug)
    || a.reportType.localeCompare(b.reportType)
    || a.language.localeCompare(b.language)
  ))
}

async function fetchAllRows<T>(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  queryFactory: () => any,
  pageSize: number,
): Promise<T[]> {
  const rows: T[] = []
  let from = 0
  while (true) {
    const to = from + pageSize - 1
    const { data, error } = await queryFactory().range(from, to)
    if (error) throw new Error(error.message)
    rows.push(...((data ?? []) as T[]))
    if ((data ?? []).length < pageSize) break
    from += pageSize
  }
  return rows
}

async function applyCandidates(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: any,
  candidates: CoverCandidate[],
): Promise<{ success: number; failed: number }> {
  let success = 0
  let failed = 0
  for (const candidate of candidates) {
    const { data, error } = await supabase.storage.from('slides').download(candidate.storagePath)
    if (error) {
      failed++
      console.error(`Failed download ${candidate.storagePath}: ${error.message}`)
      continue
    }
    const html = await data.text()
    const image = extractFirstEmbeddedImage(html)
    if (!image) {
      failed++
      console.error(`No embedded cover image in ${candidate.storagePath}`)
      continue
    }

    const uploadPath = candidate.coverStoragePath.replace(/\.jpg$/, `.${image.extension}`)
    const { error: uploadError } = await supabase.storage.from('slides').upload(
      uploadPath,
      image.bytes,
      {
        contentType: image.mimeType,
        cacheControl: '300',
        upsert: true,
      },
    )
    if (uploadError) {
      failed++
      console.error(`Failed upload ${uploadPath}: ${uploadError.message}`)
      continue
    }

    const { error: productError } = await supabase
      .from('products')
      .update({
        cover_image_url: candidate.coverPublicUrl.replace(/\.jpg$/, `.${image.extension}`),
        updated_at: candidate.publishedAt ?? new Date().toISOString(),
      })
      .eq('id', candidate.productId)
    if (productError) {
      failed++
      console.error(`Failed products ${candidate.productId}: ${productError.message}`)
      continue
    }
    success++
  }
  return { success, failed }
}

function printHelp(): void {
  console.log(`Usage:
  npx ts-node scripts/backfill-report-cover-image-urls.ts [options]

Options:
  --apply             Apply updates. Default is dry-run.
  --dry-run           Explicit dry-run mode.
  --slug VALUE        Limit to one tracked_projects.slug.
  --type VALUE        Limit to econ, maturity, or forensic.
  --page-size VALUE   Supabase page size. Default: 1000.
  --help              Show this help.
`)
}

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2))
  loadEnv()
  const { url, key } = getSupabaseCredentials()
  const supabase = createClient(url, key, { auth: { persistSession: false } })

  let query = supabase
    .from('project_reports')
    .select(`
      id,
      project_id,
      product_id,
      report_type,
      language,
      status,
      published_at,
      updated_at,
      created_at,
      slide_html_urls_by_lang,
      tracked_projects!inner(id, name, slug),
      products!inner(id, cover_image_url)
    `)
    .in('status', ['published', 'in_review'])
    .not('product_id', 'is', null)
    .order('updated_at', { ascending: false })
  if (options.reportType) query = query.eq('report_type', options.reportType)
  if (options.slug) query = query.eq('tracked_projects.slug', options.slug)

  const reports = await fetchAllRows<ReportRow>(() => query, options.pageSize)
  const candidates = buildReportCoverCandidates(reports, url)

  console.log('=== Report Cover Image URL Backfill ===')
  console.log(`Mode: ${options.apply ? 'APPLY' : 'DRY-RUN'}`)
  console.log(`Reports scanned: ${reports.length}`)
  console.log(`Candidates: ${candidates.length}`)
  for (const candidate of candidates.slice(0, 80)) {
    console.log(
      `- ${candidate.projectName} (${candidate.projectSlug}) ${candidate.reportType}/${candidate.language} `
      + `product=${candidate.productId} cover=${candidate.coverPublicUrl}`,
    )
  }
  if (candidates.length > 80) console.log(`... ${candidates.length - 80} more`)

  if (!options.apply) {
    console.log('\nDry-run complete. Re-run with --apply in the approved remote path to write updates.')
    return
  }

  const result = await applyCandidates(supabase, candidates)
  console.log(`\nApplied cover backfill: success=${result.success} failed=${result.failed}`)
  if (result.failed > 0) process.exitCode = 1
}

if (process.argv[1]?.endsWith('backfill-report-cover-image-urls.ts')) {
  main().catch(error => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
