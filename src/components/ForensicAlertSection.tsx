'use server'

import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import ForensicCardPreview from './ForensicCardPreview'

interface ForensicReport {
  id: string
  project_id: string
  card_data: Record<string, any>
  card_summary_en: string
  card_keywords: string[]
  card_risk_score: number
  tracked_projects: {
    id: string
    name: string
    slug: string
    symbol: string
  }
}

export default async function ForensicAlertSection() {
  try {
    const supabase = await createServerSupabaseClient()

    const { data: reports, error } = await supabase
      .from('project_reports')
      .select(
        `
        id,
        project_id,
        card_data,
        card_summary_en,
        card_keywords,
        card_risk_score,
        tracked_projects!inner(
          id,
          name,
          slug,
          symbol
        )
      `
      )
      .eq('report_type', 'forensic')
      .in('status', ['published', 'coming_soon'])
      .in('card_qa_status', ['approved', 'pending'])
      .not('card_data', 'is', null)
      .order('published_at', { ascending: false })
      .limit(3)

    if (error || !reports || reports.length === 0) {
      return null
    }

    const validReports = reports.filter(
      (report): report is ForensicReport =>
        report.tracked_projects !== null &&
        report.card_data !== null &&
        typeof report.card_data === 'object'
    )

    if (validReports.length === 0) {
      return null
    }

    return (
      <section className="py-12 md:py-16 px-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
            🔍 Latest Forensic Alerts
          </h2>
          <p className="text-lg text-gray-400">Real-time market anomaly detection</p>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {validReports.map((report) => {
            const riskLevel = report.card_data?.risk_level ?? 'Elevated'
            const change24h = report.card_data?.price_change_24h ?? report.card_data?.change_24h ?? 0
            const summaryText =
              report.card_summary_en ||
              report.card_data?.summary ||
              'Forensic analysis in progress...'

            return (
              <ForensicCardPreview
                key={report.id}
                reportId={report.id}
                slug={report.tracked_projects.slug}
                projectName={report.tracked_projects.name}
                symbol={report.tracked_projects.symbol}
                change24h={change24h}
                riskLevel={riskLevel as 'Critical' | 'High' | 'Elevated'}
                riskScore={report.card_risk_score ?? 0}
                keywords={report.card_keywords ?? []}
                summaryText={summaryText}
              />
            )
          })}
        </div>

        {/* CTA Link */}
        <div className="flex justify-center">
          <Link
            href="/reports?type=forensic"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-red-900/30 hover:bg-red-900/50 border border-red-900/50 text-red-400 hover:text-red-300 transition-all duration-200 font-medium group"
          >
            <span>View All Forensic Reports</span>
            <span className="group-hover:translate-x-1 transition-transform">→</span>
          </Link>
        </div>
      </section>
    )
  } catch (error) {
    console.error('[ForensicAlertSection] Error fetching reports:', error)
    return null
  }
}
