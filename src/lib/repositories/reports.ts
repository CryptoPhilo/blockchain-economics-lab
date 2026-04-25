import { SupabaseClient } from '@supabase/supabase-js'
import type {
  ProjectReport,
  TrackedProject,
  ReportType,
  ReportStatus,
  SupportedLanguage
} from '../types'

/**
 * Repository for report-related data access
 * Encapsulates all database queries for reports
 */
export class ReportsRepository {
  constructor(private supabase: SupabaseClient) {}

  private getEffectiveReportDate(report: Pick<ProjectReport, 'published_at' | 'created_at'>) {
    return report.published_at || report.created_at || null
  }

  /**
   * Fetch a single report by ID with optional project join
   */
  async getReportById(reportId: string, includeProject = true) {
    const selectQuery = includeProject ? '*' : '*'
    const query = this.supabase
      .from('project_reports')
      .select(selectQuery)
      .eq('id', reportId)
      .single()

    const { data, error } = await query

    if (error) {
      throw new Error(`Failed to fetch report: ${error.message}`)
    }

    // Fetch project separately if needed
    if (includeProject && data) {
      const { data: project } = await this.supabase
        .from('tracked_projects')
        .select('*')
        .eq('id', data.project_id)
        .single()

      return { ...data, project } as unknown as ProjectReport
    }

    return data as unknown as ProjectReport | null
  }

  /**
   * Fetch the latest forensic report for a project by slug
   */
  async getLatestForensicReportBySlug(slug: string) {
    // First get the project
    const { data: project, error: projectError } = await this.supabase
      .from('tracked_projects')
      .select('*')
      .eq('slug', slug)
      .single()

    if (projectError || !project) {
      return null
    }

    // Then get the latest report
    const { data: report, error: reportError } = await this.supabase
      .from('project_reports')
      .select('*')
      .eq('project_id', project.id)
      .eq('report_type', 'forensic')
      .in('status', ['published', 'coming_soon'])
      .order('published_at', { ascending: false })
      .limit(1)
      .single()

    if (reportError) {
      return null
    }

    return {
      report: report as ProjectReport,
      project: project as TrackedProject
    }
  }

  async getHomepageForensicReports(limit = 8) {
    const { data, error } = await this.supabase
      .from('project_reports')
      .select('*, tracked_projects!inner(id, name, slug, symbol, chain, category)')
      .eq('report_type', 'forensic')
      .eq('status', 'published')
      .not('card_data', 'is', null)
      .order('published_at', { ascending: false })
      .limit(limit)

    if (error) {
      throw new Error(`Failed to fetch homepage reports: ${error.message}`)
    }

    return data || []
  }

  /**
   * Fetch paginated reports with filters
   */
  async getReports(params: {
    reportType?: ReportType
    status?: ReportStatus | ReportStatus[]
    searchQuery?: string
    page?: number
    pageSize?: number
    createdAfter?: Date
    orderBy?: { column: string; ascending: boolean }
  }) {
    const {
      reportType = 'forensic',
      status = ['published', 'coming_soon'],
      searchQuery,
      page = 1,
      pageSize = 20,
      createdAfter,
      orderBy = { column: 'created_at', ascending: false }
    } = params
    const usesEffectiveDateOrdering =
      orderBy.column === 'created_at' || orderBy.column === 'published_at'

    // Build count query
    let countQuery = this.supabase
      .from('project_reports')
      .select('id', { count: 'exact', head: true })
      .eq('report_type', reportType)

    // Build data query
    let dataQuery = this.supabase
      .from('project_reports')
      .select('*, project:tracked_projects(id, name, slug, symbol, chain, category)')
      .eq('report_type', reportType)

    // Apply status filter
    if (Array.isArray(status)) {
      countQuery = countQuery.in('status', status)
      dataQuery = dataQuery.in('status', status)
    } else {
      countQuery = countQuery.eq('status', status)
      dataQuery = dataQuery.eq('status', status)
    }

    // Apply date filter
    if (createdAfter) {
      const effectiveDateFilter =
        `published_at.gte.${createdAfter.toISOString()},and(published_at.is.null,created_at.gte.${createdAfter.toISOString()})`
      countQuery = countQuery.or(effectiveDateFilter)
      dataQuery = dataQuery.or(effectiveDateFilter)
    }

    // Apply search filter
    if (searchQuery && searchQuery.trim()) {
      const q = `%${searchQuery.trim()}%`
      countQuery = countQuery.ilike('title_en', q)
      dataQuery = dataQuery.ilike('title_en', q)
    }

    if (!usesEffectiveDateOrdering) {
      dataQuery = dataQuery.order(orderBy.column, { ascending: orderBy.ascending })

      const from = (page - 1) * pageSize
      const to = from + pageSize - 1
      dataQuery = dataQuery.range(from, to)
    }

    // Execute queries
    const [{ count }, { data, error }] = await Promise.all([
      countQuery,
      dataQuery,
    ])

    if (error) {
      throw new Error(`Failed to fetch reports: ${error.message}`)
    }

    const reports = (data || []) as ProjectReport[]

    if (usesEffectiveDateOrdering) {
      const sortedReports = [...reports].sort((a, b) => {
        const aTime = this.getEffectiveReportDate(a)
        const bTime = this.getEffectiveReportDate(b)
        const aValue = aTime ? new Date(aTime).getTime() : 0
        const bValue = bTime ? new Date(bTime).getTime() : 0
        return orderBy.ascending ? aValue - bValue : bValue - aValue
      })

      const from = (page - 1) * pageSize
      const to = from + pageSize

      return {
        reports: sortedReports.slice(from, to),
        totalCount: count || 0,
        totalPages: Math.ceil((count || 0) / pageSize),
        currentPage: page
      }
    }

    return {
      reports,
      totalCount: count || 0,
      totalPages: Math.ceil((count || 0) / pageSize),
      currentPage: page
    }
  }

  /**
   * Get report file URL with language fallback
   */
  getReportFileUrl(
    report: ProjectReport,
    locale: SupportedLanguage,
    preferDownload = false
  ): string | null {
    const gdriveByLang = (report.gdrive_urls_by_lang || {}) as Record<string, unknown>
    const filesByLang = (report.file_urls_by_lang || {}) as Record<string, string>

    // Helper to resolve URL from entry
    const resolveUrl = (val: unknown): string | undefined => {
      if (typeof val === 'string') return val
      if (val && typeof val === 'object' && 'url' in val) {
        const entry = val as { url: string; download_url?: string }
        return preferDownload ? (entry.download_url || entry.url) : entry.url
      }
      return undefined
    }

    // Try requested language first
    let fileUrl: string | null = resolveUrl(gdriveByLang[locale]) || filesByLang[locale] || null

    // Fallback to English
    if (!fileUrl && locale !== 'en') {
      fileUrl = resolveUrl(gdriveByLang['en']) || filesByLang['en'] || null
    }

    // Fallback to report-level URLs
    if (!fileUrl) {
      fileUrl = preferDownload
        ? (report.gdrive_download_url || report.gdrive_url || report.file_url || null)
        : (report.gdrive_url || report.file_url || null)
    }

    return fileUrl
  }

  /**
   * Check if user has access to a report
   */
  async checkReportAccess(reportId: string, userId?: string) {
    const report = await this.getReportById(reportId, false)

    if (!report) {
      return { hasAccess: false, reason: 'report_not_found' }
    }

    // If report has no product or product is free, allow access
    if (!report.product_id) {
      return { hasAccess: true, report }
    }

    // Fetch product details
    const { data: product } = await this.supabase
      .from('products')
      .select('*')
      .eq('id', report.product_id)
      .single()

    if (!product || product.price_usd_cents === 0) {
      return { hasAccess: true, report }
    }

    // Check if user is authenticated
    if (!userId) {
      return { hasAccess: false, reason: 'authentication_required', report }
    }

    // Check user library
    const { data: access } = await this.supabase
      .from('user_library')
      .select('id, download_count')
      .eq('user_id', userId)
      .eq('product_id', product.id)
      .maybeSingle()

    if (!access) {
      return { hasAccess: false, reason: 'purchase_required', report }
    }

    return {
      hasAccess: true,
      report,
      libraryId: access.id,
      downloadCount: access.download_count ?? 0,
    }
  }
}

/**
 * Create a reports repository instance
 */
export function createReportsRepository(supabase: SupabaseClient) {
  return new ReportsRepository(supabase)
}
