import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { sendEmail } from '@/lib/email'

/**
 * POST /api/forensic-lead
 * Email collection and gated PDF delivery for forensic reports.
 * Captures lead email, inserts into email_leads table, sends download link via Resend.
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'https://bcelab.xyz'

interface ForensicLeadRequest {
  email: string
  reportId: string
}

interface ForensicLeadResponse {
  success: boolean
  message?: string
  error?: string
}

/**
 * Validate email format using standard regex
 */
function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email) && email.length <= 254
}

export async function POST(request: NextRequest): Promise<NextResponse<ForensicLeadResponse>> {
  try {
    // Parse request body
    let body: ForensicLeadRequest
    try {
      body = await request.json()
    } catch {
      return NextResponse.json(
        { success: false, error: 'Invalid JSON in request body' },
        { status: 400 }
      )
    }

    const { email, reportId } = body

    // Validate inputs
    if (!email || !reportId) {
      return NextResponse.json(
        { success: false, error: 'Email and reportId are required' },
        { status: 400 }
      )
    }

    if (!isValidEmail(email)) {
      return NextResponse.json({ success: false, error: 'Invalid email format' }, { status: 400 })
    }

    // Initialize Supabase client
    const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

    // Fetch report details to get PDF link and project info
    const { data: report, error: reportError } = await supabase
      .from('project_reports')
      .select(
        `
        id,
        project_id,
        gdrive_urls_by_lang,
        tracked_projects(
          name,
          slug,
          symbol
        )
      `
      )
      .eq('id', reportId)
      .eq('report_type', 'forensic')
      .in('status', ['published', 'coming_soon'])
      .single()

    if (reportError || !report) {
      console.error('[ForensicLead] Report not found:', reportId)
      return NextResponse.json(
        { success: false, error: 'Report not found or not available' },
        { status: 404 }
      )
    }

    // Extract PDF URL from gdrive_urls_by_lang (default to 'en')
    const gdriveUrls = (report.gdrive_urls_by_lang || {}) as Record<string, string>
    const pdfUrl = gdriveUrls.en || gdriveUrls[Object.keys(gdriveUrls)[0]] || null

    if (!pdfUrl) {
      console.error('[ForensicLead] No PDF URL available for report:', reportId)
      return NextResponse.json(
        {
          success: false,
          error: 'Report PDF is not yet available. Please check back soon.',
        },
        { status: 503 }
      )
    }

    // Insert into email_leads table
    const { data: lead, error: leadError } = await supabase.from('email_leads').insert({
      email: email.toLowerCase(),
      report_id: reportId,
      source: 'for_card',
      created_at: new Date().toISOString(),
    })

    if (leadError) {
      console.error('[ForensicLead] Database insert error:', leadError)
      // Still send email even if lead tracking fails
    }

    // Prepare and send email with download link
    const projectName = report.tracked_projects?.name || 'Forensic Report'
    const projectSymbol = report.tracked_projects?.symbol || ''

    const htmlContent = `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e5e7eb; padding: 40px 20px;">
  <div style="max-width: 560px; margin: 0 auto;">
    <!-- Header -->
    <div style="text-align: center; margin-bottom: 32px;">
      <div style="display: inline-block; width: 48px; height: 48px; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #9333ea); text-align: center; line-height: 48px; color: white; font-weight: bold; font-size: 20px;">B</div>
      <h1 style="color: white; font-size: 24px; margin: 16px 0 8px;">Your Forensic Report is Ready</h1>
      <p style="color: #9ca3af; font-size: 14px; margin: 0;">Blockchain Economics Lab</p>
    </div>

    <!-- Content Card -->
    <div style="background: rgba(255,255,255,0.05); border: 1px solid rgba(107, 114, 128, 0.3); border-radius: 16px; padding: 32px;">
      <p style="color: #e5e7eb; font-size: 16px; margin: 0 0 24px; line-height: 1.6;">
        Thank you for your interest in our forensic analysis. Your exclusive forensic report for <strong>${projectName}</strong> is now ready for download.
      </p>

      <div style="background: rgba(220, 38, 38, 0.1); border: 1px solid rgba(220, 38, 38, 0.3); border-radius: 12px; padding: 16px; margin-bottom: 24px;">
        <p style="color: #fca5a5; font-size: 13px; margin: 0;">
          ⚠️ <strong>Forensic Analysis Report</strong><br>
          Project: ${projectSymbol}<br>
          Format: PDF
        </p>
      </div>

      <a href="${pdfUrl}" style="display: inline-block; width: 100%; padding: 16px 32px; background: linear-gradient(135deg, #dc2626, #b91c1c); color: white; text-decoration: none; border-radius: 12px; font-weight: 600; font-size: 16px; text-align: center; margin-bottom: 16px;">
        📥 Download Your Report
      </a>

      <p style="color: #9ca3af; font-size: 12px; text-align: center; margin: 16px 0;">
        Direct link expires in 30 days
      </p>
    </div>

    <!-- Footer -->
    <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center;">
      <p style="color: #6b7280; font-size: 12px; margin: 0 0 12px;">
        Questions? Visit our <a href="${APP_URL}/reports?type=forensic" style="color: #6366f1; text-decoration: underline;">forensic reports page</a> to learn more.
      </p>
      <p style="color: #4b5563; font-size: 11px; margin: 0;">
        © 2026 Blockchain Economics Lab · bcelab.xyz<br>
        This content is for informational purposes only. Not financial advice.
      </p>
    </div>
  </div>
</body>
</html>`

    const emailResult = await sendEmail({
      to: email,
      subject: '[BCE Lab] Your Forensic Report is Ready',
      html: htmlContent,
      tags: [
        { name: 'type', value: 'forensic_lead' },
        { name: 'report_id', value: reportId },
        { name: 'project', value: projectSymbol || projectName },
      ],
    })

    if (!emailResult.success) {
      console.error('[ForensicLead] Email send failed:', emailResult.error)
      return NextResponse.json(
        {
          success: false,
          error: 'Failed to send email. Please try again later.',
        },
        { status: 500 }
      )
    }

    return NextResponse.json({
      success: true,
      message: 'Check your email for the download link',
    })
  } catch (error) {
    console.error('[ForensicLead] Unexpected error:', error)
    return NextResponse.json(
      {
        success: false,
        error: 'An unexpected error occurred. Please try again later.',
      },
      { status: 500 }
    )
  }
}
