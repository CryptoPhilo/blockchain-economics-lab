import { createClient } from '@supabase/supabase-js'
import fs from 'node:fs'
import path from 'node:path'

type Mode = 'dry-run' | 'apply'

type StorageObject = {
  name: string
  id?: string | null
  updated_at?: string | null
  created_at?: string | null
  metadata?: Record<string, unknown> | null
}

type ListedObject = {
  path: string
  size: number
  updatedAt: string | null
}

type ReportRow = {
  slide_html_urls_by_lang?: Record<string, unknown> | null
  cover_image_urls_by_lang?: Record<string, unknown> | null
}

const BUCKET = 'slides'
const DEFAULT_OUTPUT = 'scripts/pipeline/output/slide-storage-cleanup-report.json'
const VERSIONED_REPORT_RE = /^(econ|mat|for)\/[^/]+\/\d+\/[^/]+\.html$/i
const VERSIONED_ASSET_RE = /^(econ|mat|for)\/[^/]+\/\d+\/[^/]+_assets\/.+$/i
const LATEST_RE = /^(econ|mat|for)\/[^/]+\/latest\/.+$/i

function argValue(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  if (index === -1) return undefined
  return process.argv[index + 1]
}

function hasArg(name: string): boolean {
  return process.argv.includes(name)
}

function storageObjectSize(obj: StorageObject): number {
  const metadata = obj.metadata ?? {}
  const candidates = [
    metadata.size,
    metadata.contentLength,
    metadata.content_length,
    metadata.ContentLength,
  ]
  for (const value of candidates) {
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value)
  }
  return 0
}

function classifyObject(objectPath: string): string {
  if (VERSIONED_REPORT_RE.test(objectPath)) return 'versioned_html'
  if (VERSIONED_ASSET_RE.test(objectPath)) return 'versioned_asset'
  if (LATEST_RE.test(objectPath)) return 'latest'
  if (/\/latest\/[^/]+-cover\.(png|jpe?g|webp)$/i.test(objectPath)) return 'cover'
  return 'other'
}

function storagePathFromPublicUrl(value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim()) return null
  try {
    const url = new URL(value)
    const marker = `/storage/v1/object/public/${BUCKET}/`
    const index = url.pathname.indexOf(marker)
    if (index === -1) return null
    return decodeURIComponent(url.pathname.slice(index + marker.length))
  } catch {
    return null
  }
}

function collectReferencedPaths(rows: ReportRow[]): Set<string> {
  const paths = new Set<string>()
  for (const row of rows) {
    for (const map of [row.slide_html_urls_by_lang, row.cover_image_urls_by_lang]) {
      if (!map || typeof map !== 'object') continue
      for (const value of Object.values(map)) {
        const storagePath = storagePathFromPublicUrl(value)
        if (storagePath) paths.add(storagePath)
      }
    }
  }
  return paths
}

function summarize(objects: ListedObject[]): Record<string, { count: number; bytes: number }> {
  const summary: Record<string, { count: number; bytes: number }> = {}
  for (const object of objects) {
    const key = classifyObject(object.path)
    summary[key] ??= { count: 0, bytes: 0 }
    summary[key].count += 1
    summary[key].bytes += object.size
  }
  return summary
}

async function loadReportRows(supabase: ReturnType<typeof createClient>): Promise<ReportRow[]> {
  const rows: ReportRow[] = []
  const pageSize = 1000
  for (let from = 0; ; from += pageSize) {
    const to = from + pageSize - 1
    const { data, error } = await supabase
      .from('project_reports')
      .select('slide_html_urls_by_lang, cover_image_urls_by_lang')
      .range(from, to)
    if (error) throw new Error(`project_reports fetch failed: ${error.message}`)
    rows.push(...((data ?? []) as ReportRow[]))
    if (!data || data.length < pageSize) break
  }
  return rows
}

async function listStorageObjects(
  supabase: ReturnType<typeof createClient>,
  prefix = '',
): Promise<ListedObject[]> {
  const out: ListedObject[] = []
  const pageSize = 1000
  for (let offset = 0; ; offset += pageSize) {
    const { data, error } = await supabase.storage.from(BUCKET).list(prefix, {
      limit: pageSize,
      offset,
      sortBy: { column: 'name', order: 'asc' },
    })
    if (error) throw new Error(`storage list failed at '${prefix || '/'}': ${error.message}`)
    const entries = (data ?? []) as StorageObject[]
    for (const entry of entries) {
      const entryPath = prefix ? `${prefix}/${entry.name}` : entry.name
      if (entry.id) {
        out.push({
          path: entryPath,
          size: storageObjectSize(entry),
          updatedAt: entry.updated_at ?? null,
        })
      } else {
        out.push(...await listStorageObjects(supabase, entryPath))
      }
    }
    if (entries.length < pageSize) break
  }
  return out
}

function batch<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = []
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size))
  }
  return chunks
}

async function removeObjects(
  supabase: ReturnType<typeof createClient>,
  candidates: ListedObject[],
): Promise<{ deleted: number; failed: Array<{ path: string; message: string }> }> {
  let deleted = 0
  const failed: Array<{ path: string; message: string }> = []
  for (const paths of batch(candidates.map((item) => item.path), 100)) {
    const { data, error } = await supabase.storage.from(BUCKET).remove(paths)
    if (error) {
      for (const p of paths) failed.push({ path: p, message: error.message })
      continue
    }
    deleted += data?.length ?? paths.length
  }
  return { deleted, failed }
}

async function main(): Promise<void> {
  const mode = (argValue('--mode') ?? 'dry-run') as Mode
  const output = argValue('--output') ?? DEFAULT_OUTPUT
  const confirmDelete = hasArg('--confirm-delete')
  if (!['dry-run', 'apply'].includes(mode)) {
    throw new Error(`Unsupported --mode '${mode}'`)
  }
  if (mode === 'apply' && !confirmDelete) {
    throw new Error('Refusing apply without --confirm-delete')
  }

  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!supabaseUrl || !supabaseKey) {
    throw new Error('SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY are required')
  }

  const supabase = createClient(supabaseUrl, supabaseKey, { auth: { persistSession: false } })
  const reportRows = await loadReportRows(supabase)
  const referencedPaths = collectReferencedPaths(reportRows)
  const beforeObjects = await listStorageObjects(supabase)
  const candidates = beforeObjects.filter((object) => (
    (VERSIONED_REPORT_RE.test(object.path) || VERSIONED_ASSET_RE.test(object.path))
    && !referencedPaths.has(object.path)
  ))

  let deletionResult: Awaited<ReturnType<typeof removeObjects>> | null = null
  let afterObjects: ListedObject[] | null = null
  if (mode === 'apply') {
    deletionResult = await removeObjects(supabase, candidates)
    afterObjects = await listStorageObjects(supabase)
  }

  const beforeBytes = beforeObjects.reduce((sum, item) => sum + item.size, 0)
  const candidateBytes = candidates.reduce((sum, item) => sum + item.size, 0)
  const afterBytes = afterObjects?.reduce((sum, item) => sum + item.size, 0) ?? null
  const report = {
    generatedAt: new Date().toISOString(),
    mode,
    bucket: BUCKET,
    reportRows: reportRows.length,
    referencedPathCount: referencedPaths.size,
    before: {
      objectCount: beforeObjects.length,
      bytes: beforeBytes,
      byClass: summarize(beforeObjects),
    },
    candidates: {
      objectCount: candidates.length,
      bytes: candidateBytes,
      byClass: summarize(candidates),
      sample: candidates.slice(0, 50),
    },
    deletion: deletionResult,
    after: afterObjects ? {
      objectCount: afterObjects.length,
      bytes: afterBytes,
      byClass: summarize(afterObjects),
    } : null,
    freedBytes: afterBytes === null ? null : beforeBytes - afterBytes,
  }

  fs.mkdirSync(path.dirname(output), { recursive: true })
  fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`)
  console.log(JSON.stringify(report, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
