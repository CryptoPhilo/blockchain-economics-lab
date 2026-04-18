#!/usr/bin/env node
/**
 * BCE-352: Audit and sync ECON/FOR report timestamps
 *
 * This script audits report timestamp mismatches between:
 * - project_reports (actual report documents)
 * - tracked_projects (timestamp fields for badge display)
 *
 * It identifies projects with reports but NULL timestamps.
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
  console.error(`NEXT_PUBLIC_SUPABASE_URL: ${supabaseUrl ? 'set' : 'missing'}`)
  console.error(`SUPABASE_SERVICE_KEY: ${supabaseKey ? 'set' : 'missing'}`)
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

interface ReportSummary {
  projectId: string
  projectName: string
  projectSlug: string
  reportType: 'econ' | 'maturity' | 'forensic'
  reportCount: number
  latestPublishedAt: string | null
  reportStatus: string[]
  fileUrls: string[]
  trackedTimestamp: string | null
  hasMismatch: boolean
}

async function auditReportTimestamps() {
  console.log('=== BCE-352: Report Timestamp Audit ===\n')
  console.log('Checking for mismatches between project_reports and tracked_projects timestamps...\n')

  // 1. Get all project reports with their status
  console.log('📊 Fetching all project reports...')
  const { data: reports, error: reportsError } = await supabase
    .from('project_reports')
    .select('id, project_id, report_type, status, published_at, file_url, created_at')
    .order('published_at', { ascending: false })

  if (reportsError) {
    console.error('❌ Error fetching project_reports:', reportsError)
    return
  }

  console.log(`✅ Found ${reports?.length || 0} total reports\n`)

  // 2. Get all tracked projects with timestamp fields
  console.log('📊 Fetching tracked projects with timestamp fields...')
  const { data: projects, error: projectsError } = await supabase
    .from('tracked_projects')
    .select('id, name, slug, last_econ_report_at, last_maturity_report_at, last_forensic_report_at')

  if (projectsError) {
    console.error('❌ Error fetching tracked_projects:', projectsError)
    return
  }

  console.log(`✅ Found ${projects?.length || 0} tracked projects\n`)

  // 3. Build a map of projects by ID
  const projectMap = new Map(projects?.map(p => [p.id, p]) || [])

  // 4. Group reports by project and type
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const reportsByProject = new Map<string, Map<string, any[]>>()

  reports?.forEach(report => {
    if (!reportsByProject.has(report.project_id)) {
      reportsByProject.set(report.project_id, new Map())
    }
    const projectReports = reportsByProject.get(report.project_id)!

    if (!projectReports.has(report.report_type)) {
      projectReports.set(report.report_type, [])
    }
    projectReports.get(report.report_type)!.push(report)
  })

  // 5. Analyze mismatches
  const mismatches: ReportSummary[] = []
  const reportTypes: ('econ' | 'maturity' | 'forensic')[] = ['econ', 'maturity', 'forensic']

  reportsByProject.forEach((reportsByType, projectId) => {
    const project = projectMap.get(projectId)
    if (!project) {
      console.warn(`⚠️  Project ${projectId} not found in tracked_projects`)
      return
    }

    reportTypes.forEach(reportType => {
      const reports = reportsByType.get(reportType) || []
      if (reports.length === 0) return

      // Get published/coming_soon reports
      const publishedReports = reports.filter(r =>
        r.status === 'published' || r.status === 'coming_soon'
      )

      // Get the latest published_at timestamp
      const latestPublishedAt = publishedReports
        .map(r => r.published_at)
        .filter(Boolean)
        .sort()
        .reverse()[0] || null

      // Get tracked timestamp
      const timestampField = reportType === 'econ'
        ? 'last_econ_report_at'
        : reportType === 'maturity'
        ? 'last_maturity_report_at'
        : 'last_forensic_report_at'

      const trackedTimestamp = project[timestampField]

      // Check for mismatch
      const hasMismatch = publishedReports.length > 0 && !trackedTimestamp

      if (hasMismatch) {
        mismatches.push({
          projectId,
          projectName: project.name,
          projectSlug: project.slug,
          reportType,
          reportCount: reports.length,
          latestPublishedAt,
          reportStatus: reports.map(r => r.status),
          fileUrls: reports.map(r => r.file_url).filter(Boolean),
          trackedTimestamp,
          hasMismatch: true
        })
      }
    })
  })

  // 6. Print summary
  console.log('=== AUDIT SUMMARY ===\n')
  console.log(`Total reports in database: ${reports?.length || 0}`)
  console.log(`Total tracked projects: ${projects?.length || 0}`)
  console.log(`Projects with timestamp mismatches: ${mismatches.length}\n`)

  // 7. Print detailed mismatches
  if (mismatches.length > 0) {
    console.log('=== TIMESTAMP MISMATCHES ===')
    console.log('Projects with published reports but NULL timestamps:\n')

    const groupedByType = {
      econ: mismatches.filter(m => m.reportType === 'econ'),
      maturity: mismatches.filter(m => m.reportType === 'maturity'),
      forensic: mismatches.filter(m => m.reportType === 'forensic')
    }

    Object.entries(groupedByType).forEach(([type, items]) => {
      if (items.length === 0) return

      console.log(`\n📝 ${type.toUpperCase()} Reports (${items.length} projects):`)
      console.log('─'.repeat(80))

      items.forEach((item, idx) => {
        console.log(`${idx + 1}. ${item.projectName} (${item.projectSlug})`)
        console.log(`   Project ID: ${item.projectId}`)
        console.log(`   Report count: ${item.reportCount}`)
        console.log(`   Report statuses: ${item.reportStatus.join(', ')}`)
        console.log(`   Latest published_at: ${item.latestPublishedAt || 'NULL'}`)
        console.log(`   Tracked timestamp: ${item.trackedTimestamp || 'NULL ❌'}`)
        console.log(`   File URLs: ${item.fileUrls.length > 0 ? item.fileUrls.join(', ') : 'None'}`)
        console.log()
      })
    })

    // 8. Generate summary statistics
    console.log('\n=== STATISTICS BY REPORT TYPE ===')
    console.log(`ECON reports with NULL timestamps: ${groupedByType.econ.length}`)
    console.log(`Maturity reports with NULL timestamps: ${groupedByType.maturity.length}`)
    console.log(`Forensic reports with NULL timestamps: ${groupedByType.forensic.length}`)

    // 9. Write report to file
    const reportData = {
      auditDate: new Date().toISOString(),
      totalReports: reports?.length || 0,
      totalProjects: projects?.length || 0,
      mismatchCount: mismatches.length,
      mismatches,
      summary: {
        econ: groupedByType.econ.length,
        maturity: groupedByType.maturity.length,
        forensic: groupedByType.forensic.length
      }
    }

    const fs = await import('fs/promises')
    await fs.writeFile(
      'report-timestamp-audit.json',
      JSON.stringify(reportData, null, 2)
    )

    console.log('\n✅ Detailed report saved to: report-timestamp-audit.json')

  } else {
    console.log('✅ No timestamp mismatches found! All reports have correct timestamps.')
  }

  // 10. Additional checks
  console.log('\n=== ADDITIONAL CHECKS ===')

  // Check for reports with NULL published_at
  const reportsWithNullPublishedAt = reports?.filter(r =>
    (r.status === 'published' || r.status === 'coming_soon') && !r.published_at
  ) || []

  if (reportsWithNullPublishedAt.length > 0) {
    console.log(`\n⚠️  Found ${reportsWithNullPublishedAt.length} published reports with NULL published_at:`)
    reportsWithNullPublishedAt.forEach(r => {
      const project = projectMap.get(r.project_id)
      console.log(`   - ${project?.name || 'Unknown'} (${r.report_type}) - Status: ${r.status}`)
    })
  } else {
    console.log('✅ All published reports have published_at timestamps')
  }

  // Check for reports with file_url but wrong status
  const reportsWithFilesButNotPublished = reports?.filter(r =>
    r.file_url && r.status !== 'published' && r.status !== 'coming_soon'
  ) || []

  if (reportsWithFilesButNotPublished.length > 0) {
    console.log(`\n⚠️  Found ${reportsWithFilesButNotPublished.length} reports with file_url but not published:`)
    reportsWithFilesButNotPublished.forEach(r => {
      const project = projectMap.get(r.project_id)
      console.log(`   - ${project?.name || 'Unknown'} (${r.report_type}) - Status: ${r.status}`)
    })
  }

  console.log('\n=== AUDIT COMPLETE ===')
}

// Run the audit
auditReportTimestamps().catch(console.error)
