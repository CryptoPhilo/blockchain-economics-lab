#!/usr/bin/env node
/**
 * Sync tracked_projects report timestamps from project_reports.
 *
 * Default mode is dry-run. Use --apply to write corrections. Unlike the older
 * BCE-352 script, this corrects stale timestamps as well as NULL values.
 */

import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'
import { existsSync } from 'fs'
import { join } from 'path'

export type ReportType = 'econ' | 'maturity' | 'forensic'

export interface ReportTimestampRow {
  id: string
  project_id: string
  report_type: ReportType
  status: string | null
  published_at: string | null
  updated_at: string | null
  created_at: string | null
  card_data?: unknown
}

export interface TrackedProjectTimestampRow {
  id: string
  name: string
  slug: string
  last_econ_report_at: string | null
  last_maturity_report_at: string | null
  last_forensic_report_at: string | null
}

export interface SyncUpdate {
  projectId: string
  projectName: string
  projectSlug: string
  reportId: string
  reportType: ReportType
  timestampField: keyof Pick<
    TrackedProjectTimestampRow,
    'last_econ_report_at' | 'last_maturity_report_at' | 'last_forensic_report_at'
  >
  oldTimestamp: string | null
  newTimestamp: string
  source: string
  reason: 'missing' | 'stale'
}

export interface ReportPublishUpdate {
  reportId: string
  projectId: string
  reportType: ReportType
  oldPublishedAt: string | null
  newPublishedAt: string
  source: 'card_data.generated_at'
}

export interface SyncOptions {
  apply: boolean
  pageSize: number
}

const REPORT_TYPES: ReportType[] = ['econ', 'maturity', 'forensic']
const ACTIVE_STATUSES = new Set(['published', 'coming_soon'])

function isReportType(value: unknown): value is ReportType {
  return typeof value === 'string' && REPORT_TYPES.includes(value as ReportType)
}

function isValidTimestamp(value: string): boolean {
  return !Number.isNaN(new Date(value).getTime())
}

export function timestampFieldForReportType(reportType: ReportType): SyncUpdate['timestampField'] {
  if (reportType === 'econ') return 'last_econ_report_at'
  if (reportType === 'maturity') return 'last_maturity_report_at'
  return 'last_forensic_report_at'
}

export function resolveReportTimestamp(
  report: Pick<ReportTimestampRow, 'published_at' | 'updated_at' | 'created_at' | 'card_data'>,
): { timestamp: string; source: string } | null {
  const cardData = report.card_data
  if (cardData && typeof cardData === 'object' && !Array.isArray(cardData)) {
    const generatedAt = (cardData as Record<string, unknown>).generated_at
    if (typeof generatedAt === 'string' && generatedAt.trim() && isValidTimestamp(generatedAt)) {
      return { timestamp: generatedAt, source: 'card_data.generated_at' }
    }
  }
  if (report.published_at && isValidTimestamp(report.published_at)) {
    return { timestamp: report.published_at, source: 'published_at' }
  }
  if (report.updated_at && isValidTimestamp(report.updated_at)) {
    return { timestamp: report.updated_at, source: 'updated_at' }
  }
  if (report.created_at && isValidTimestamp(report.created_at)) {
    return { timestamp: report.created_at, source: 'created_at' }
  }
  return null
}

export function isNewerTimestamp(left: string, right: string): boolean {
  return new Date(left).getTime() > new Date(right).getTime()
}

export function buildTimestampUpdates(
  reports: ReportTimestampRow[],
  projects: TrackedProjectTimestampRow[],
): SyncUpdate[] {
  const projectMap = new Map(projects.map(project => [project.id, project]))
  const latestReports = new Map<string, { report: ReportTimestampRow; timestamp: string; source: string }>()

  for (const report of reports) {
    if (!ACTIVE_STATUSES.has(String(report.status ?? ''))) continue
    if (!isReportType(report.report_type)) continue

    const resolved = resolveReportTimestamp(report)
    if (!resolved) continue

    const key = `${report.project_id}:${report.report_type}`
    const existing = latestReports.get(key)
    if (!existing || isNewerTimestamp(resolved.timestamp, existing.timestamp)) {
      latestReports.set(key, { report, ...resolved })
    }
  }

  const updates: SyncUpdate[] = []

  for (const { report, timestamp, source } of latestReports.values()) {
    const project = projectMap.get(report.project_id)
    if (!project) continue

    const timestampField = timestampFieldForReportType(report.report_type)
    const oldTimestamp = project[timestampField]
    if (oldTimestamp === timestamp) continue

    if (oldTimestamp && !isNewerTimestamp(timestamp, oldTimestamp)) continue

    const reason: SyncUpdate['reason'] = !oldTimestamp ? 'missing' : 'stale'

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
      reason,
    })
  }

  return updates.sort((a, b) => (
    a.reportType.localeCompare(b.reportType)
    || a.projectSlug.localeCompare(b.projectSlug)
  ))
}

export function buildReportPublishUpdates(reports: ReportTimestampRow[]): ReportPublishUpdate[] {
  const updates: ReportPublishUpdate[] = []

  for (const report of reports) {
    if (!ACTIVE_STATUSES.has(String(report.status ?? ''))) continue
    if (!isReportType(report.report_type)) continue
    if (!report.card_data || typeof report.card_data !== 'object' || Array.isArray(report.card_data)) continue

    const generatedAt = (report.card_data as Record<string, unknown>).generated_at
    if (typeof generatedAt !== 'string' || !generatedAt.trim()) continue

    const oldTime = report.published_at ? new Date(report.published_at).getTime() : 0
    const newTime = new Date(generatedAt).getTime()
    if (Number.isNaN(newTime) || newTime - oldTime <= 60_000) continue

    updates.push({
      reportId: report.id,
      projectId: report.project_id,
      reportType: report.report_type,
      oldPublishedAt: report.published_at,
      newPublishedAt: generatedAt,
      source: 'card_data.generated_at',
    })
  }

  return updates.sort((a, b) => (
    a.reportType.localeCompare(b.reportType)
    || String(a.reportId).localeCompare(String(b.reportId))
  ))
}

export function parseArgs(argv: string[]): SyncOptions {
  const options: SyncOptions = { apply: false, pageSize: 1000 }

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    const next = argv[i + 1]

    if (arg === '--apply') {
      options.apply = true
    } else if (arg === '--dry-run') {
      options.apply = false
    } else if (arg === '--page-size') {
      options.pageSize = parsePositiveInteger(arg, next)
      i++
    } else if (arg.startsWith('--page-size=')) {
      options.pageSize = parsePositiveInteger('--page-size', arg.slice('--page-size='.length))
    } else if (arg === '--help' || arg === '-h') {
      printHelp()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  return options
}

function parsePositiveInteger(name: string, value: string | undefined): number {
  if (!value || value.startsWith('--')) throw new Error(`${name} requires a positive integer`)
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`${name} must be a positive integer`)
  return parsed
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

async function applyUpdates(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: any,
  updates: SyncUpdate[],
): Promise<{ success: number; failed: number }> {
  let success = 0
  let failed = 0

  for (const update of updates) {
    const { error } = await supabase
      .from('tracked_projects')
      .update({
        [update.timestampField]: update.newTimestamp,
        updated_at: new Date().toISOString(),
      })
      .eq('id', update.projectId)

    if (error) {
      failed++
      console.error(`Failed to update ${update.projectSlug}: ${error.message}`)
    } else {
      success++
    }
  }

  return { success, failed }
}

async function applyReportPublishUpdates(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: any,
  updates: ReportPublishUpdate[],
): Promise<{ success: number; failed: number }> {
  let success = 0
  let failed = 0

  for (const update of updates) {
    const { error } = await supabase
      .from('project_reports')
      .update({
        published_at: update.newPublishedAt,
        updated_at: update.newPublishedAt,
      })
      .eq('id', update.reportId)

    if (error) {
      failed++
      console.error(`Failed to update report ${update.reportId}: ${error.message}`)
    } else {
      success++
    }
  }

  return { success, failed }
}

function printHelp(): void {
  console.log(`Usage:
  npx ts-node scripts/sync-report-timestamps.ts [options]

Options:
  --apply             Apply updates. Default is dry-run.
  --dry-run           Explicit dry-run mode.
  --page-size VALUE   Supabase page size. Default: 1000.
  --help              Show this help.
`)
}

function printSummary(updates: SyncUpdate[]): void {
  const byReason = updates.reduce<Record<string, number>>((acc, update) => {
    acc[update.reason] = (acc[update.reason] ?? 0) + 1
    return acc
  }, {})
  const byType = updates.reduce<Record<string, number>>((acc, update) => {
    acc[update.reportType] = (acc[update.reportType] ?? 0) + 1
    return acc
  }, {})

  console.log(`Planned corrections: ${updates.length}`)
  console.log(`By reason: ${JSON.stringify(byReason)}`)
  console.log(`By report_type: ${JSON.stringify(byType)}`)
  for (const update of updates.slice(0, 50)) {
    console.log(
      `- ${update.projectName} (${update.projectSlug}) ${update.reportType}: `
      + `${update.oldTimestamp ?? 'NULL'} -> ${update.newTimestamp} `
      + `(${update.source}, ${update.reason})`,
    )
  }
  if (updates.length > 50) console.log(`... ${updates.length - 50} more`)
}

function printReportPublishSummary(updates: ReportPublishUpdate[]): void {
  const byType = updates.reduce<Record<string, number>>((acc, update) => {
    acc[update.reportType] = (acc[update.reportType] ?? 0) + 1
    return acc
  }, {})

  console.log(`Report published_at corrections: ${updates.length}`)
  console.log(`Report corrections by type: ${JSON.stringify(byType)}`)
  for (const update of updates.slice(0, 50)) {
    console.log(
      `- report ${update.reportId} ${update.reportType}: `
      + `${update.oldPublishedAt ?? 'NULL'} -> ${update.newPublishedAt} (${update.source})`,
    )
  }
  if (updates.length > 50) console.log(`... ${updates.length - 50} more`)
}

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2))
  loadEnv()

  const { url, key } = getSupabaseCredentials()
  const supabase = createClient(url, key, { auth: { persistSession: false } })

  const reports = await fetchAllRows<ReportTimestampRow>(
    () => supabase
      .from('project_reports')
      .select('id, project_id, report_type, status, published_at, updated_at, created_at, card_data')
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

  const updates = buildTimestampUpdates(reports, projects)
  const reportPublishUpdates = buildReportPublishUpdates(reports)

  console.log('=== Report Timestamp Sync ===')
  console.log(`Mode: ${options.apply ? 'APPLY' : 'DRY-RUN'}`)
  console.log(`Reports scanned: ${reports.length}`)
  console.log(`Projects scanned: ${projects.length}`)
  printSummary(updates)
  printReportPublishSummary(reportPublishUpdates)

  if (!options.apply) {
    console.log('\nDry-run complete. Re-run with --apply to write corrections.')
    return
  }

  const result = await applyUpdates(supabase, updates)
  const reportResult = await applyReportPublishUpdates(supabase, reportPublishUpdates)
  console.log(`\nApplied tracked project corrections: success=${result.success} failed=${result.failed}`)
  console.log(`Applied report published_at corrections: success=${reportResult.success} failed=${reportResult.failed}`)
  if (result.failed > 0 || reportResult.failed > 0) process.exitCode = 1
}

if (process.argv[1]?.endsWith('sync-report-timestamps.ts')) {
  main().catch(error => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
