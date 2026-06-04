import fs from 'node:fs'
import path from 'node:path'

import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'

import { reportSupportsLocale, pickLocaleReport } from '../src/lib/report-locale'
import { getLocalizedCardSummary } from '../src/lib/report-summary'
import { sortReportsLatestFirst } from '../src/lib/report-versioning'
import type { ProjectReport, ReportType, TrackedProject } from '../src/lib/types'

const SUPPORTED_LOCALES = ['ko', 'en', 'ja', 'zh', 'fr', 'es', 'de'] as const
const PAGE_SIZE = 1000

const SELECT_FIELDS = [
  'id',
  'project_id',
  'report_type',
  'version',
  'status',
  'language',
  'is_latest',
  'published_at',
  'updated_at',
  'created_at',
  'card_summary_en',
  'card_summary_ko',
  'card_summary_fr',
  'card_summary_es',
  'card_summary_de',
  'card_summary_ja',
  'card_summary_zh',
  'card_data',
  'file_urls_by_lang',
  'gdrive_urls_by_lang',
  'slide_html_urls_by_lang',
  'project:tracked_projects(id,slug,name,symbol,status)',
].join(',')

type ProjectReportWithProject = ProjectReport & {
  project?: Pick<TrackedProject, 'id' | 'slug' | 'name' | 'symbol' | 'status'> | null
}

type Finding = {
  id: string
  project_id: string
  project_slug?: string
  project_name?: string
  project_symbol?: string
  report_type: ReportType
  version: number
  language?: string | null
  locale: string
  status: string
  is_latest?: boolean
  published_at?: string | null
  reason: string
  english_fallback_available?: boolean
}

function loadEnv() {
  const candidates = [
    process.env.BCE_ENV_FILE,
    '.env.local',
    '.env',
  ].filter((value): value is string => Boolean(value))

  for (const candidate of candidates) {
    const resolved = path.resolve(candidate)
    if (fs.existsSync(resolved)) {
      config({ path: resolved })
    }
  }
}

function getArgValue(name: string): string | null {
  const index = process.argv.indexOf(name)
  if (index === -1) return null
  return process.argv[index + 1] ?? null
}

function hasEnglishFallbackSummary(report: ProjectReport): boolean {
  return Boolean(getLocalizedCardSummary(report, 'en', { allowEnglishFallback: true }))
}

function makeFinding(
  report: ProjectReportWithProject,
  locale: string,
  reason: string,
): Finding {
  return {
    id: report.id,
    project_id: report.project_id,
    project_slug: report.project?.slug,
    project_name: report.project?.name,
    project_symbol: report.project?.symbol,
    report_type: report.report_type,
    version: Number(report.version || 0),
    language: report.language,
    locale,
    status: report.status,
    is_latest: report.is_latest,
    published_at: report.published_at ?? null,
    reason,
    english_fallback_available: hasEnglishFallbackSummary(report),
  }
}

function countBy<T>(
  rows: T[],
  keyFn: (row: T) => string,
): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const row of rows) {
    const key = keyFn(row)
    counts[key] = (counts[key] ?? 0) + 1
  }
  return Object.fromEntries(Object.entries(counts).sort((a, b) => a[0].localeCompare(b[0])))
}

async function fetchReports() {
  loadEnv()

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL
  const supabaseKey = process.env.SUPABASE_SERVICE_KEY
    || process.env.SUPABASE_SERVICE_ROLE_KEY
    || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    throw new Error('Missing Supabase credentials. Set BCE_ENV_FILE or Supabase env vars.')
  }

  const supabase = createClient(supabaseUrl, supabaseKey, {
    auth: { persistSession: false },
  })

  const rows: ProjectReportWithProject[] = []
  for (let from = 0; ; from += PAGE_SIZE) {
    const to = from + PAGE_SIZE - 1
    const { data, error } = await supabase
      .from('project_reports')
      .select(SELECT_FIELDS)
      .in('status', ['published', 'in_review'])
      .range(from, to)

    if (error) throw error

    rows.push(...(((data || []) as unknown) as ProjectReportWithProject[]))
    if (!data || data.length < PAGE_SIZE) break
  }

  return rows
}

function auditRows(reports: ProjectReportWithProject[]): Finding[] {
  const findings: Finding[] = []

  for (const report of reports) {
    for (const locale of SUPPORTED_LOCALES) {
      if (!reportSupportsLocale(report, locale)) continue
      if (getLocalizedCardSummary(report, locale)) continue

      findings.push(makeFinding(report, locale, 'row_missing_localized_card_summary'))
    }
  }

  return findings
}

function auditSelectedProjectCards(reports: ProjectReportWithProject[]): Finding[] {
  const groups = new Map<string, ProjectReportWithProject[]>()
  for (const report of reports) {
    const key = `${report.project_id}:${report.report_type}`
    groups.set(key, [...(groups.get(key) ?? []), report])
  }

  const findings: Finding[] = []

  for (const group of groups.values()) {
    for (const locale of SUPPORTED_LOCALES) {
      const eligible = sortReportsLatestFirst(
        group.filter((report) => reportSupportsLocale(report, locale)),
      )
      const selected = pickLocaleReport(eligible, locale)
      if (!selected) continue
      if (getLocalizedCardSummary(selected, locale)) continue

      findings.push(makeFinding(selected, locale, 'selected_project_card_missing_summary'))
    }
  }

  return findings
}

async function main() {
  const reports = await fetchReports()
  const rowFindings = auditRows(reports)
  const selectedProjectCardFindings = auditSelectedProjectCards(reports)

  const output = {
    generated_at: new Date().toISOString(),
    rows_seen: reports.length,
    row_findings: rowFindings.length,
    selected_project_card_findings_count: selectedProjectCardFindings.length,
    row_findings_by_locale: countBy(rowFindings, (finding) => finding.locale),
    row_findings_by_type: countBy(rowFindings, (finding) => finding.report_type),
    selected_findings_by_locale: countBy(selectedProjectCardFindings, (finding) => finding.locale),
    selected_findings_by_type: countBy(selectedProjectCardFindings, (finding) => finding.report_type),
    selected_project_card_findings: selectedProjectCardFindings,
    row_findings_sample: rowFindings.slice(0, 50),
  }

  const json = `${JSON.stringify(output, null, 2)}\n`
  const outPath = getArgValue('--out')
  if (outPath) {
    fs.writeFileSync(outPath, json)
  }
  process.stdout.write(json)

  if (process.argv.includes('--fail-on-findings') && selectedProjectCardFindings.length > 0) {
    process.exitCode = 1
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
