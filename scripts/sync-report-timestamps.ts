#!/usr/bin/env node
/**
 * BCE-352: Sync missing report timestamps
 *
 * This script updates tracked_projects timestamp fields for projects
 * that have published/coming_soon reports but NULL timestamps.
 *
 * Strategy:
 * - Use report's published_at if available
 * - Fall back to report's updated_at or created_at
 * - Only update projects identified in the audit
 *
 * Usage:
 *   npx tsx scripts/sync-report-timestamps.ts [--dry-run]
 */

import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'
import { join } from 'path'

// Load .env.local
config({ path: join(__dirname, '..', '.env.local') })

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ Missing Supabase credentials in environment')
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

interface SyncUpdate {
  projectId: string
  projectName: string
  reportType: 'econ' | 'maturity' | 'forensic'
  timestampField: string
  newTimestamp: string
  source: string
}

async function syncReportTimestamps(dryRun: boolean = false) {
  console.log('=== BCE-352: Sync Report Timestamps ===\n')
  console.log(`Mode: ${dryRun ? '🔍 DRY RUN (no changes will be made)' : '✍️  LIVE UPDATE'}\n`)

  // 1. Get all project reports that are published or coming_soon
  console.log('📊 Fetching reports with published/coming_soon status...')
  const { data: reports, error: reportsError } = await supabase
    .from('project_reports')
    .select('id, project_id, report_type, status, published_at, updated_at, created_at')
    .in('status', ['published', 'coming_soon'])
    .order('published_at', { ascending: false })

  if (reportsError) {
    console.error('❌ Error fetching reports:', reportsError)
    return
  }

  console.log(`✅ Found ${reports?.length || 0} published/coming_soon reports\n`)

  // 2. Get all tracked projects
  const { data: projects, error: projectsError } = await supabase
    .from('tracked_projects')
    .select('id, name, slug, last_econ_report_at, last_maturity_report_at, last_forensic_report_at')

  if (projectsError) {
    console.error('❌ Error fetching projects:', projectsError)
    return
  }

  const projectMap = new Map(projects?.map(p => [p.id, p]) || [])

  // 3. Group reports by project and type, keeping only the latest per type
  const latestReportsByProject = new Map<string, Map<string, any>>()

  reports?.forEach(report => {
    if (!latestReportsByProject.has(report.project_id)) {
      latestReportsByProject.set(report.project_id, new Map())
    }
    const projectReports = latestReportsByProject.get(report.project_id)!

    // Only keep the latest report per type
    const existingReport = projectReports.get(report.report_type)
    if (!existingReport) {
      projectReports.set(report.report_type, report)
    } else {
      // Compare timestamps to keep the latest
      const existingTime = existingReport.published_at || existingReport.updated_at || existingReport.created_at
      const currentTime = report.published_at || report.updated_at || report.created_at
      if (currentTime > existingTime) {
        projectReports.set(report.report_type, report)
      }
    }
  })

  // 4. Identify updates needed
  const updates: SyncUpdate[] = []
  const reportTypes: ('econ' | 'maturity' | 'forensic')[] = ['econ', 'maturity', 'forensic']

  latestReportsByProject.forEach((reportsByType, projectId) => {
    const project = projectMap.get(projectId)
    if (!project) return

    reportTypes.forEach(reportType => {
      const report = reportsByType.get(reportType)
      if (!report) return

      const timestampField = reportType === 'econ'
        ? 'last_econ_report_at'
        : reportType === 'maturity'
        ? 'last_maturity_report_at'
        : 'last_forensic_report_at'

      const trackedTimestamp = project[timestampField]

      // Determine the timestamp to use
      let newTimestamp: string | null = null
      let source = ''

      if (report.published_at) {
        newTimestamp = report.published_at
        source = 'published_at'
      } else if (report.updated_at) {
        newTimestamp = report.updated_at
        source = 'updated_at'
      } else if (report.created_at) {
        newTimestamp = report.created_at
        source = 'created_at'
      }

      // Only update if tracked timestamp is NULL and we have a new timestamp
      if (!trackedTimestamp && newTimestamp) {
        updates.push({
          projectId,
          projectName: project.name,
          reportType,
          timestampField,
          newTimestamp,
          source
        })
      }
    })
  })

  // 5. Display planned updates
  console.log('=== PLANNED UPDATES ===\n')
  console.log(`Total projects to update: ${updates.length}\n`)

  if (updates.length === 0) {
    console.log('✅ No updates needed! All timestamps are in sync.')
    return
  }

  // Group by type
  const updatesByType = {
    econ: updates.filter(u => u.reportType === 'econ'),
    maturity: updates.filter(u => u.reportType === 'maturity'),
    forensic: updates.filter(u => u.reportType === 'forensic')
  }

  Object.entries(updatesByType).forEach(([type, items]) => {
    if (items.length === 0) return

    console.log(`\n📝 ${type.toUpperCase()} (${items.length} updates):`)
    console.log('─'.repeat(80))

    items.forEach((update, idx) => {
      console.log(`${idx + 1}. ${update.projectName}`)
      console.log(`   Field: ${update.timestampField}`)
      console.log(`   New timestamp: ${update.newTimestamp} (from ${update.source})`)
    })
  })

  console.log('\n')
  console.log('=== SUMMARY ===')
  console.log(`ECON updates: ${updatesByType.econ.length}`)
  console.log(`Maturity updates: ${updatesByType.maturity.length}`)
  console.log(`Forensic updates: ${updatesByType.forensic.length}`)
  console.log(`Total: ${updates.length}`)

  // 6. Apply updates (if not dry run)
  if (dryRun) {
    console.log('\n🔍 DRY RUN MODE: No changes were made')
    console.log('Run without --dry-run to apply these updates')
    return
  }

  console.log('\n✍️  Applying updates...\n')

  let successCount = 0
  let errorCount = 0

  for (const update of updates) {
    try {
      const { error } = await supabase
        .from('tracked_projects')
        .update({ [update.timestampField]: update.newTimestamp })
        .eq('id', update.projectId)

      if (error) {
        console.error(`❌ Failed to update ${update.projectName}:`, error.message)
        errorCount++
      } else {
        console.log(`✅ Updated ${update.projectName} (${update.reportType})`)
        successCount++
      }
    } catch (err) {
      console.error(`❌ Error updating ${update.projectName}:`, err)
      errorCount++
    }
  }

  console.log('\n=== UPDATE COMPLETE ===')
  console.log(`✅ Successful updates: ${successCount}`)
  if (errorCount > 0) {
    console.log(`❌ Failed updates: ${errorCount}`)
  }
  console.log(`\nTotal processed: ${successCount + errorCount} of ${updates.length}`)
}

// Parse command line args
const args = process.argv.slice(2)
const dryRun = args.includes('--dry-run')

// Run the sync
syncReportTimestamps(dryRun).catch(console.error)
