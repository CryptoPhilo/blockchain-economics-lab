#!/usr/bin/env node
/**
 * Backfill project_reports.cover_image_urls_by_lang from report slide HTML.
 *
 * Default mode is dry-run. Use --apply only in the approved remote execution
 * path because this uploads Storage objects and updates production rows.
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
  cover_image_urls_by_lang?: unknown
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
  productId: string | null
  projectSlug: string
  projectName: string
  reportType: ReportType
  language: string
  htmlUrl: string
  storagePath: string
  coverStoragePath: string
  coverPublicUrl: string
  oldCoverUrl: string | null
  oldReportCoverUrl: string | null
  shouldUpdateProductCover: boolean
  publishedAt: string | null
}

interface Options {
  apply: boolean
  pageSize: number
  slug?: string
  reportType?: ReportType
  force: boolean
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

const IMAGE_EXTENSION_TO_MIME: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
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
  const options: Options = { apply: false, pageSize: 1000, force: false }
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    const next = argv[i + 1]
    if (arg === '--apply') {
      options.apply = true
    } else if (arg === '--dry-run') {
      options.apply = false
    } else if (arg === '--force') {
      options.force = true
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

export function getSlideHtmlUrls(report: ReportRow): Record<string, string> {
  const urls = isPlainObject(report.slide_html_urls_by_lang) ? report.slide_html_urls_by_lang : {}
  return Object.fromEntries(
    Object.entries(urls)
      .filter((entry): entry is [string, string] => isNonEmptyString(entry[0]) && isNonEmptyString(entry[1]))
      .map(([language, url]) => [language.trim(), url.trim()]),
  )
}

export function getReportCoverUrls(report: ReportRow): Record<string, string> {
  const urls = isPlainObject(report.cover_image_urls_by_lang) ? report.cover_image_urls_by_lang : {}
  return Object.fromEntries(
    Object.entries(urls)
      .filter((entry): entry is [string, string] => isNonEmptyString(entry[0]) && isNonEmptyString(entry[1]))
      .map(([language, url]) => [language.trim(), url.trim()]),
  )
}

export function mergeCoverImageUrlsByLang(
  existing: unknown,
  language: string,
  coverUrl: string,
): Record<string, string> {
  return {
    ...(isPlainObject(existing) ? getReportCoverUrls({ cover_image_urls_by_lang: existing } as ReportRow) : {}),
    [language]: coverUrl,
  }
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

export function extractFirstExternalSlideImageUrl(html: string): string | null {
  const slidesMatch = html.match(/const\s+slides\s*=\s*\[([\s\S]*?)\]\s*;/)
  const candidates: string[] = []
  const collectQuotedUrls = (source: string) => {
    const quotedStringPattern = /(['"`])((?:\\.|(?!\1).)+)\1/g
    let match: RegExpExecArray | null
    while ((match = quotedStringPattern.exec(source)) !== null) {
      candidates.push(match[2].replace(/\\\//g, '/').replace(/&amp;/g, '&'))
    }
  }

  if (slidesMatch) collectQuotedUrls(slidesMatch[1])

  const imgSrcPattern = /<img\b[^>]*\bsrc=(['"])(.*?)\1/gi
  let imgMatch: RegExpExecArray | null
  while ((imgMatch = imgSrcPattern.exec(html)) !== null) {
    candidates.push(imgMatch[2].replace(/&amp;/g, '&'))
  }

  return candidates.find(url => /^https?:\/\//i.test(url) && /\.(?:png|jpe?g|webp)(?:[?#].*)?$/i.test(url)) ?? null
}

function extensionFromImageUrl(url: string): string | null {
  const pathname = new URL(url).pathname.toLowerCase()
  const match = pathname.match(/\.([a-z0-9]+)$/)
  if (!match) return null
  const extension = match[1] === 'jpeg' ? 'jpg' : match[1]
  return IMAGE_EXTENSION_TO_MIME[extension] ? extension : null
}

async function downloadExternalImage(url: string): Promise<{ mimeType: string; bytes: Buffer; extension: string } | null> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  const headerMime = response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase()
  const extension = headerMime && IMAGE_MIME_TO_EXTENSION[headerMime]
    ? IMAGE_MIME_TO_EXTENSION[headerMime]
    : extensionFromImageUrl(url)
  if (!extension) return null
  return {
    mimeType: IMAGE_EXTENSION_TO_MIME[extension],
    bytes: Buffer.from(await response.arrayBuffer()),
    extension,
  }
}

export function buildReportCoverCandidates(
  reports: ReportRow[],
  supabaseUrl: string,
  options: { force?: boolean } = {},
): CoverCandidate[] {
  const candidates: CoverCandidate[] = []
  for (const report of reports) {
    if (report.status !== 'published' && report.status !== 'in_review') continue
    const product = report.products
    const project = report.tracked_projects
    if (!project?.slug) continue
    const slideUrls = getSlideHtmlUrls(report)
    const existingCoverUrls = getReportCoverUrls(report)
    const preferredLanguage = getPreferredReportLanguage(report)
    const storageType = STORAGE_TYPE_BY_REPORT_TYPE[report.report_type]
    for (const [language, htmlUrl] of Object.entries(slideUrls).sort(([a], [b]) => a.localeCompare(b))) {
      if (!options.force && isNonEmptyString(existingCoverUrls[language])) continue
      const storagePath = storagePathFromPublicSlidesUrl(htmlUrl)
      if (!storagePath) continue

      const coverStoragePath = `${storageType}/${project.slug}/latest/${language}-cover.jpg`
      candidates.push({
        reportId: report.id,
        productId: report.product_id ?? null,
        projectSlug: project.slug,
        projectName: project.name,
        reportType: report.report_type,
        language,
        htmlUrl,
        storagePath,
        coverStoragePath,
        coverPublicUrl: publicUrlForStoragePath(supabaseUrl, coverStoragePath),
        oldCoverUrl: product?.cover_image_url ?? null,
        oldReportCoverUrl: existingCoverUrls[language] ?? null,
        shouldUpdateProductCover: Boolean(
          report.product_id
          && !isNonEmptyString(product?.cover_image_url)
          && language === preferredLanguage,
        ),
        publishedAt: report.published_at || report.updated_at || report.created_at,
      })
    }
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
): Promise<{ success: number; failed: number; productUpdates: number }> {
  let success = 0
  let failed = 0
  let productUpdates = 0
  for (const candidate of candidates) {
    const { data, error } = await supabase.storage.from('slides').download(candidate.storagePath)
    if (error) {
      failed++
      console.error(`Failed download ${candidate.storagePath}: ${error.message}`)
      continue
    }
    const html = await data.text()
    let image = extractFirstEmbeddedImage(html)
    let sourceImageUrl: string | null = null
    if (!image) {
      sourceImageUrl = extractFirstExternalSlideImageUrl(html)
      if (!sourceImageUrl) {
        failed++
        console.error(`No cover image source in ${candidate.storagePath}`)
        continue
      }
      try {
        image = await downloadExternalImage(sourceImageUrl)
      } catch (error) {
        failed++
        const message = error instanceof Error ? error.message : String(error)
        console.error(`Failed download cover image ${sourceImageUrl}: ${message}`)
        continue
      }
      if (!image) {
        failed++
        console.error(`Unsupported cover image source in ${candidate.storagePath}: ${sourceImageUrl}`)
        continue
      }
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
    let coverPublicUrl = candidate.coverPublicUrl.replace(/\.jpg$/, `.${image.extension}`)
    if (uploadError) {
      if (!sourceImageUrl) {
        failed++
        console.error(`Failed upload ${uploadPath}: ${uploadError.message}`)
        continue
      }
      console.error(`Failed upload ${uploadPath}: ${uploadError.message}; using source slide image ${sourceImageUrl}`)
      coverPublicUrl = sourceImageUrl
    }

    const current = await supabase
      .from('project_reports')
      .select('cover_image_urls_by_lang')
      .eq('id', candidate.reportId)
      .maybeSingle()
    if (current.error) {
      failed++
      console.error(`Failed fetch project_reports ${candidate.reportId}: ${current.error.message}`)
      continue
    }
    const coverUrls = mergeCoverImageUrlsByLang(
      current.data?.cover_image_urls_by_lang,
      candidate.language,
      coverPublicUrl,
    )
    const { error: reportError } = await supabase
      .from('project_reports')
      .update({
        cover_image_urls_by_lang: coverUrls,
        updated_at: candidate.publishedAt ?? new Date().toISOString(),
      })
      .eq('id', candidate.reportId)
    if (reportError) {
      failed++
      console.error(`Failed project_reports ${candidate.reportId}: ${reportError.message}`)
      continue
    }

    if (candidate.productId && candidate.shouldUpdateProductCover) {
      const { error: productError } = await supabase
        .from('products')
        .update({
          cover_image_url: coverPublicUrl,
          updated_at: candidate.publishedAt ?? new Date().toISOString(),
        })
        .eq('id', candidate.productId)
      if (productError) {
        failed++
        console.error(`Failed products ${candidate.productId}: ${productError.message}`)
        continue
      }
      productUpdates++
    }
    success++
  }
  return { success, failed, productUpdates }
}

function printHelp(): void {
  console.log(`Usage:
  npx ts-node scripts/backfill-report-cover-image-urls.ts [options]

Options:
  --apply             Apply updates. Default is dry-run.
  --dry-run           Explicit dry-run mode.
  --force             Rebuild covers even when project_reports already has a URL for the language.
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
      cover_image_urls_by_lang,
      tracked_projects!inner(id, name, slug),
      products(id, cover_image_url)
    `)
    .in('status', ['published', 'in_review'])
    .order('updated_at', { ascending: false })
  if (options.reportType) query = query.eq('report_type', options.reportType)
  if (options.slug) query = query.eq('tracked_projects.slug', options.slug)

  const reports = await fetchAllRows<ReportRow>(() => query, options.pageSize)
  const candidates = buildReportCoverCandidates(reports, url, { force: options.force })

  console.log('=== Report Cover Image URL Backfill ===')
  console.log(`Mode: ${options.apply ? 'APPLY' : 'DRY-RUN'}`)
  console.log(`Force: ${options.force ? 'yes' : 'no'}`)
  console.log(`Reports scanned: ${reports.length}`)
  console.log(`Candidates: ${candidates.length}`)
  for (const candidate of candidates.slice(0, 80)) {
    console.log(
      `- ${candidate.projectName} (${candidate.projectSlug}) ${candidate.reportType}/${candidate.language} `
      + `report=${candidate.reportId} product=${candidate.productId || '-'} cover=${candidate.coverPublicUrl}`,
    )
  }
  if (candidates.length > 80) console.log(`... ${candidates.length - 80} more`)

  if (!options.apply) {
    console.log('\nDry-run complete. Re-run with --apply in the approved remote path to write updates.')
    return
  }

  const result = await applyCandidates(supabase, candidates)
  console.log(
    `\nApplied cover backfill: success=${result.success} failed=${result.failed} `
    + `productUpdates=${result.productUpdates}`,
  )
  if (result.failed > 0) process.exitCode = 1
}

if (process.argv[1]?.endsWith('backfill-report-cover-image-urls.ts')) {
  main().catch(error => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
