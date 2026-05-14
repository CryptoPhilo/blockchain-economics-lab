#!/usr/bin/env node
/**
 * Audit report slide HTML and timestamp metadata.
 *
 * Produces a read-only JSON report covering:
 * - rows with Drive/PDF URLs but missing slide_html_urls_by_lang
 * - rows where Storage has latest/*.html objects missing from DB metadata
 * - report/tracked_project timestamp mismatches
 */

import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'
import { existsSync } from 'fs'
import { writeFile } from 'fs/promises'
import { join } from 'path'

type JsonMap = Record<string, unknown>
type ReportType = 'econ' | 'maturity' | 'forensic'

interface ReportTimestampRow {
  id: string
  project_id: string
  report_type: ReportType
  status: string | null
  published_at: string | null
  updated_at: string | null
  created_at: string | null
  card_data?: unknown
}

interface TrackedProjectTimestampRow {
  id: string
  name: string
  slug: string
  last_econ_report_at: string | null
  last_maturity_report_at: string | null
  last_forensic_report_at: string | null
}

interface TimestampUpdate {
  projectId: string
  projectName: string
  projectSlug: string
  reportId: string
  reportType: ReportType
  timestampField: 'last_econ_report_at' | 'last_maturity_report_at' | 'last_forensic_report_at'
  oldTimestamp: string | null
  newTimestamp: string
  source: string
  reason: 'missing' | 'stale'
}

interface ProjectReportAuditRow extends ReportTimestampRow {
  language: string | null
  gdrive_url: string | null
  gdrive_urls_by_lang: unknown
  file_url: string | null
  file_urls_by_lang: unknown
  slide_html_urls_by_lang: unknown
}

interface AuditOptions {
  output: string
  pageSize: number
}

interface StorageSlideObject {
  lang: string
  updatedAt: string | null
  path: string
}

const STORAGE_TYPE_BY_REPORT_TYPE: Record<string, string> = {
  econ: 'econ',
  maturity: 'mat',
  forensic: 'for',
}

const LANGS = ['ko', 'en', 'fr', 'es', 'de', 'ja', 'zh']
const ACTIVE_STATUSES = new Set(['published', 'coming_soon'])

export function hasMeaningfulUrl(value: unknown): boolean {
  if (typeof value === 'string') return value.trim().length > 0
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  return Object.values(value as JsonMap).some(hasMeaningfulUrl)
}

export function getUrlLangs(value: unknown): string[] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return []
  return LANGS.filter(lang => hasMeaningfulUrl((value as JsonMap)[lang]))
}

export function getMissingSlideHtmlLangs(row: ProjectReportAuditRow): string[] {
  const sourceLangs = new Set([
    ...getUrlLangs(row.gdrive_urls_by_lang),
    ...getUrlLangs(row.file_urls_by_lang),
  ])
  if (hasMeaningfulUrl(row.gdrive_url) || hasMeaningfulUrl(row.file_url)) {
    sourceLangs.add(row.language || 'unknown')
  }

  const slideLangs = new Set(getUrlLangs(row.slide_html_urls_by_lang))
  return [...sourceLangs].filter(lang => lang !== 'unknown' && !slideLangs.has(lang)).sort()
}

function isForComingSoonPlaceholderWithoutAsset(row: ProjectReportAuditRow): boolean {
  return (
    row.report_type === 'forensic'
    && row.status === 'coming_soon'
    && !hasMeaningfulUrl(row.gdrive_url)
    && !hasMeaningfulUrl(row.gdrive_urls_by_lang)
    && !hasMeaningfulUrl(row.file_url)
    && !hasMeaningfulUrl(row.file_urls_by_lang)
    && !hasMeaningfulUrl(row.slide_html_urls_by_lang)
  )
}

function timestampFieldForReportType(reportType: ReportType): TimestampUpdate['timestampField'] {
  if (reportType === 'econ') return 'last_econ_report_at'
  if (reportType === 'maturity') return 'last_maturity_report_at'
  return 'last_forensic_report_at'
}

function resolveReportTimestamp(
  report: Pick<ReportTimestampRow, 'published_at' | 'updated_at' | 'created_at' | 'card_data'>,
): { timestamp: string; source: string } | null {
  const cardData = report.card_data
  if (cardData && typeof cardData === 'object' && !Array.isArray(cardData)) {
    const generatedAt = (cardData as Record<string, unknown>).generated_at
    if (typeof generatedAt === 'string' && generatedAt.trim()) {
      return { timestamp: generatedAt, source: 'card_data.generated_at' }
    }
  }
  if (report.published_at) return { timestamp: report.published_at, source: 'published_at' }
  if (report.updated_at) return { timestamp: report.updated_at, source: 'updated_at' }
  if (report.created_at) return { timestamp: report.created_at, source: 'created_at' }
  return null
}

function isNewerTimestamp(left: string, right: string): boolean {
  return new Date(left).getTime() > new Date(right).getTime()
}

function buildTimestampUpdates(
  reports: ReportTimestampRow[],
  projects: TrackedProjectTimestampRow[],
): TimestampUpdate[] {
  const projectMap = new Map(projects.map(project => [project.id, project]))
  const latestReports = new Map<string, { report: ReportTimestampRow; timestamp: string; source: string }>()

  for (const report of reports) {
    if (!ACTIVE_STATUSES.has(String(report.status ?? ''))) continue
    const resolved = resolveReportTimestamp(report)
    if (!resolved) continue

    const key = `${report.project_id}:${report.report_type}`
    const existing = latestReports.get(key)
    if (!existing || isNewerTimestamp(resolved.timestamp, existing.timestamp)) {
      latestReports.set(key, { report, ...resolved })
    }
  }

  const updates: TimestampUpdate[] = []
  for (const { report, timestamp, source } of latestReports.values()) {
    const project = projectMap.get(report.project_id)
    if (!project) continue

    const timestampField = timestampFieldForReportType(report.report_type)
    const oldTimestamp = project[timestampField]
    if (oldTimestamp === timestamp) continue
    if (oldTimestamp && !isNewerTimestamp(timestamp, oldTimestamp)) continue

    updates.push({
      projectId: project.id,
      projectName: project.name,
      projectSlug: project.slug,
      reportId: report.id,
      reportType: report.report_type,
      timestampField,
      oldTimestamp,
      newTimestamp: timestamp,
      source,
      reason: !oldTimestamp ? 'missing' : 'stale',
    })
  }

  return updates
}

function parseArgs(argv: string[]): AuditOptions {
  const options: AuditOptions = {
    output: 'report-slide-html-timestamp-audit.json',
    pageSize: 1000,
  }

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    const next = argv[i + 1]
    if (arg === '--output') {
      if (!next || next.startsWith('--')) throw new Error('--output requires a path')
      options.output = next
      i++
    } else if (arg.startsWith('--output=')) {
      options.output = arg.slice('--output='.length)
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
    console.error(`NEXT_PUBLIC_SUPABASE_URL/SUPABASE_URL: ${url ? 'set' : 'missing'}`)
    console.error(`SUPABASE_SERVICE_KEY/SUPABASE_SERVICE_ROLE_KEY: ${key ? 'set' : 'missing'}`)
    process.exit(1)
  }
  return { url, key }
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

async function listLatestStorageSlides(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: any,
  reportType: string,
  slug: string,
): Promise<StorageSlideObject[]> {
  const storageType = STORAGE_TYPE_BY_REPORT_TYPE[reportType]
  if (!storageType || !slug) return []

  const prefix = `${storageType}/${slug}/latest`
  const { data, error } = await supabase.storage.from('slides').list(prefix, { limit: 100 })
  if (error) throw new Error(`Storage list failed for ${prefix}: ${error.message}`)

  return (data ?? [])
    .filter((item: { name?: string }) => typeof item.name === 'string' && item.name.endsWith('.html'))
    .map((item: { name: string; updated_at?: string; created_at?: string }) => ({
      lang: item.name.replace(/\.html$/, ''),
      updatedAt: item.updated_at ?? item.created_at ?? null,
      path: `${prefix}/${item.name}`,
    }))
}

function toReportTimestampRows(rows: ProjectReportAuditRow[]): ReportTimestampRow[] {
  return rows.map(row => ({
    id: row.id,
    project_id: row.project_id,
    report_type: row.report_type,
    status: row.status,
    published_at: row.published_at,
    updated_at: row.updated_at,
    created_at: row.created_at,
    card_data: row.card_data,
  }))
}

function printHelp(): void {
  console.log(`Usage:
  npx ts-node scripts/audit-report-timestamps.ts [options]

Options:
  --output PATH       JSON output path. Default: report-slide-html-timestamp-audit.json.
  --page-size VALUE   Supabase page size. Default: 1000.
  --help              Show this help.
`)
}

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2))
  loadEnv()

  const { url, key } = getSupabaseCredentials()
  const supabase = createClient(url, key, { auth: { persistSession: false } })

  const reports = await fetchAllRows<ProjectReportAuditRow>(
    () => supabase
      .from('project_reports')
      .select([
        'id',
        'project_id',
        'report_type',
        'status',
        'language',
        'published_at',
        'updated_at',
        'created_at',
        'card_data',
        'gdrive_url',
        'gdrive_urls_by_lang',
        'file_url',
        'file_urls_by_lang',
        'slide_html_urls_by_lang',
      ].join(', '))
      .in('status', ['published', 'coming_soon'])
      .order('updated_at', { ascending: false }),
    options.pageSize,
  )
  const projects = await fetchAllRows<TrackedProjectTimestampRow>(
    () => supabase
      .from('tracked_projects')
      .select('id, name, slug, last_econ_report_at, last_maturity_report_at, last_forensic_report_at')
      .order('slug', { ascending: true }),
    options.pageSize,
  )
  const projectById = new Map(projects.map(project => [project.id, project]))

  const driveUrlMissingHtml = reports
    .map(row => ({
      id: row.id,
      projectSlug: projectById.get(row.project_id)?.slug ?? null,
      reportType: row.report_type,
      language: row.language,
      missingLangs: getMissingSlideHtmlLangs(row),
      hasSlideHtml: hasMeaningfulUrl(row.slide_html_urls_by_lang),
    }))
    .filter(row => row.missingLangs.length > 0)

  const storagePresentDbMissing = []
  for (const row of reports) {
    const slug = projectById.get(row.project_id)?.slug ?? ''
    const storageObjects = await listLatestStorageSlides(supabase, row.report_type, slug)
    if (storageObjects.length === 0) continue

    const dbSlideLangs = new Set(getUrlLangs(row.slide_html_urls_by_lang))
    const missingLangs = storageObjects
      .filter(object => LANGS.includes(object.lang) && !dbSlideLangs.has(object.lang))
      .map(object => object.lang)
      .sort()

    if (missingLangs.length > 0) {
      storagePresentDbMissing.push({
        id: row.id,
        projectSlug: slug,
        reportType: row.report_type,
        language: row.language,
        missingLangs,
        storageObjects,
      })
    }
  }

  const timestampUpdates = buildTimestampUpdates(
    toReportTimestampRows(reports.filter(row => !isForComingSoonPlaceholderWithoutAsset(row))),
    projects,
  )
  const reportTimestampPolicyRows = reports
    .map(row => {
      const resolved = resolveReportTimestamp(row)
      return {
        id: row.id,
        projectSlug: projectById.get(row.project_id)?.slug ?? null,
        reportType: row.report_type,
        publishedAt: row.published_at,
        updatedAt: row.updated_at,
        policyTimestamp: resolved?.timestamp ?? null,
        policySource: resolved?.source ?? null,
      }
    })
    .filter(row => (
      row.policyTimestamp
      && row.publishedAt
      && new Date(row.policyTimestamp).getTime() - new Date(row.publishedAt).getTime() > 60_000
    ))

  const audit = {
    auditDate: new Date().toISOString(),
    totals: {
      reports: reports.length,
      projects: projects.length,
      driveUrlMissingHtml: driveUrlMissingHtml.length,
      storagePresentDbMissing: storagePresentDbMissing.length,
      trackedTimestampCorrections: timestampUpdates.length,
      reportPublishedAtPolicyMismatches: reportTimestampPolicyRows.length,
    },
    driveUrlMissingHtml,
    storagePresentDbMissing,
    trackedTimestampCorrections: timestampUpdates,
    reportPublishedAtPolicyMismatches: reportTimestampPolicyRows,
  }

  await writeFile(options.output, JSON.stringify(audit, null, 2))

  console.log('=== Report Slide HTML / Timestamp Audit ===')
  console.log(`Reports scanned: ${reports.length}`)
  console.log(`Drive/PDF URL present but DB HTML missing: ${driveUrlMissingHtml.length}`)
  console.log(`Storage latest HTML present but DB HTML missing: ${storagePresentDbMissing.length}`)
  console.log(`Tracked project timestamp corrections: ${timestampUpdates.length}`)
  console.log(`Report published_at policy mismatches: ${reportTimestampPolicyRows.length}`)
  console.log(`JSON written: ${options.output}`)
}

if (process.argv[1]?.endsWith('audit-report-timestamps.ts')) {
  main().catch(error => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
