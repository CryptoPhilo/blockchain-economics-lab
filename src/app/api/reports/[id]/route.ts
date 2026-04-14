import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'

/**
 * GET /api/reports/[id]?lang=en&download=true
 *
 * Returns the GDrive URL for a report. Checks user_library for access.
 * Falls back to EN if requested language is unavailable.
 */

// STRIX-AC-001: URL whitelist to prevent open redirect via database URLs
const ALLOWED_REDIRECT_DOMAINS = [
  'drive.google.com',
  'docs.google.com',
  'storage.googleapis.com',
  'wbqponoiyoeqlepxogcb.supabase.co', // Supabase storage
  'bcelab.xyz',
]

function isAllowedRedirectUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    // Only allow HTTPS
    if (parsed.protocol !== 'https:') return false
    // Check domain whitelist
    return ALLOWED_REDIRECT_DOMAINS.some(
      (domain) => parsed.hostname === domain || parsed.hostname.endsWith(`.${domain}`)
    )
  } catch {
    return false
  }
}
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const { searchParams } = new URL(request.url)
  const lang = searchParams.get('lang') || 'en'
  const download = searchParams.get('download') === 'true'

  const supabase = await createServerSupabaseClient()

  // Get current user
  const { data: { user } } = await supabase.auth.getUser()

  // Fetch report
  const { data: report, error } = await supabase
    .from('project_reports')
    .select('*, product:products(*)')
    .eq('id', id)
    .single()

  if (error || !report) {
    return NextResponse.json({ error: 'Report not found' }, { status: 404 })
  }

  // Check access: if product exists and has a price, verify user owns it
  const product = report.product
  if (product && product.price_usd_cents > 0) {
    if (!user) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 })
    }

    const { data: access } = await supabase
      .from('user_library')
      .select('id')
      .eq('user_id', user.id)
      .eq('product_id', product.id)
      .maybeSingle()

    if (!access) {
      return NextResponse.json({ error: 'Purchase required to access this report' }, { status: 403 })
    }

    // Track download
    await supabase
      .from('user_library')
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .update({ download_count: (access as any).download_count + 1 || 1 })
      .eq('id', access.id)
  }

  // Resolve file URL by language
  let fileUrl: string | null = null
  const gdriveByLang = report.gdrive_urls_by_lang || {}
  const filesByLang = report.file_urls_by_lang || {}

  // Try requested language first
  if (gdriveByLang[lang]) {
    const entry = gdriveByLang[lang]
    fileUrl = download
      ? (entry.download_url || entry.url)
      : entry.url
  } else if (filesByLang[lang]) {
    fileUrl = filesByLang[lang]
  }

  // Fallback to EN
  if (!fileUrl && lang !== 'en') {
    if (gdriveByLang['en']) {
      const entry = gdriveByLang['en']
      fileUrl = download
        ? (entry.download_url || entry.url)
        : entry.url
    } else if (filesByLang['en']) {
      fileUrl = filesByLang['en']
    }
  }

  // Fallback to report.gdrive_url or file_url
  if (!fileUrl) {
    fileUrl = download
      ? (report.gdrive_download_url || report.gdrive_url || report.file_url)
      : (report.gdrive_url || report.file_url)
  }

  if (!fileUrl) {
    return NextResponse.json({ error: 'Report file not available' }, { status: 404 })
  }

  // STRIX-AC-001: Validate redirect URL against domain whitelist
  if (!isAllowedRedirectUrl(fileUrl)) {
    console.error(`[Reports] Blocked redirect to untrusted URL: ${fileUrl}`)
    return NextResponse.json({ error: 'Report file URL is invalid' }, { status: 400 })
  }

  // Redirect to the file
  return NextResponse.redirect(fileUrl)
}
