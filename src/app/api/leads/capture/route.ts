import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { sendConfirmationEmail } from '@/lib/email'
import { randomBytes } from 'crypto'
import { createRateLimiter, getRateLimitId, rateLimitResponse } from '@/lib/rate-limit'

/**
 * OPS-011-T01: Lead capture API endpoint
 *
 * Unified entry point for all lead collection sources:
 * - lead_magnet: Report/content downloads gated by email
 * - newsletter: Newsletter signup from various CTAs
 * - rating_gate: Maturity score table email gate
 * - homepage: Homepage hero/footer CTA
 *
 * Flow: email validation → email_leads INSERT → subscribers UPSERT → Double Opt-in email
 */

// Rate limit: 5 lead captures per IP per hour
const leadCaptureLimiter = createRateLimiter({ windowMs: 60 * 60 * 1000, max: 5 })

type LeadSource = 'lead_magnet' | 'newsletter' | 'rating_gate' | 'homepage'

interface LeadCaptureBody {
  email: string
  name?: string
  source: LeadSource
  source_id?: string   // e.g., report_id for lead_magnet, page slug for rating_gate
  locale?: string
  referral_code?: string
}

// Simple email regex — rejects obvious junk, not a full RFC 5322 validator
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export async function POST(request: NextRequest) {
  try {
    // ── Rate limiting ──────────────────────────────────────────
    const rlId = getRateLimitId(request)
    const rlResult = leadCaptureLimiter.check(rlId)
    if (!rlResult.success) {
      return rateLimitResponse(rlResult)
    }

    // ── Parse & validate body ──────────────────────────────────
    const body: LeadCaptureBody = await request.json()
    const {
      email,
      name,
      source = 'homepage',
      source_id,
      locale = 'en',
      referral_code,
    } = body

    if (!email || !EMAIL_RE.test(email)) {
      return NextResponse.json(
        { error: 'A valid email address is required.' },
        { status: 400 },
      )
    }

    const validSources: LeadSource[] = ['lead_magnet', 'newsletter', 'rating_gate', 'homepage']
    if (!validSources.includes(source)) {
      return NextResponse.json(
        { error: `Invalid source. Must be one of: ${validSources.join(', ')}` },
        { status: 400 },
      )
    }

    const emailLower = email.toLowerCase().trim()
    const supabase = await createServerSupabaseClient()
    const country =
      request.headers.get('x-geo-country') ||
      request.headers.get('x-vercel-ip-country') ||
      ''

    // ── 1. Insert into email_leads (tracking table) ────────────
    // Always insert — even if the subscriber already exists, we want to
    // record every lead capture event for funnel analytics.
    const leadPayload: Record<string, unknown> = {
      email: emailLower,
      source,
      created_at: new Date().toISOString(),
    }
    if (source_id) {
      // email_leads.report_id is UUID — only set if source_id looks like a UUID
      const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
      if (UUID_RE.test(source_id)) {
        leadPayload.report_id = source_id
      }
    }

    const { error: leadError } = await supabase.from('email_leads').insert(leadPayload)
    if (leadError) {
      console.error('[leads/capture] email_leads insert error:', leadError)
      // Non-fatal — continue with subscriber flow
    }

    // ── 2. Upsert into subscribers (double opt-in) ─────────────
    const optInToken = randomBytes(32).toString('hex')

    const { data: existing } = await supabase
      .from('subscribers')
      .select('id, opted_in, unsubscribed, name')
      .eq('email', emailLower)
      .single()

    let subscriberStatus: 'new' | 'resubscribe' | 'already_active' = 'new'

    if (existing) {
      if (existing.opted_in && !existing.unsubscribed) {
        subscriberStatus = 'already_active'
        // Still return success — don't reveal subscription status to third parties
      } else {
        subscriberStatus = 'resubscribe'
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const updatePayload: any = {
          opted_in: false,
          unsubscribed: false,
          opt_in_token: optInToken,
          opt_in_sent_at: new Date().toISOString(),
          locale,
          ip_country: country,
          source,
        }
        if (name && !existing.name) updatePayload.name = name
        await supabase.from('subscribers').update(updatePayload).eq('id', existing.id)
      }
    } else {
      // New subscriber
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const insertPayload: any = {
        email: emailLower,
        locale,
        source,
        opted_in: false,
        opt_in_token: optInToken,
        opt_in_sent_at: new Date().toISOString(),
        ip_country: country,
      }
      if (name) insertPayload.name = name

      const { error: subError } = await supabase.from('subscribers').insert(insertPayload)
      if (subError) {
        console.error('[leads/capture] subscriber insert error:', subError)
        return NextResponse.json(
          { error: 'Failed to process subscription. Please try again.' },
          { status: 500 },
        )
      }
    }

    // ── 3. Send double opt-in confirmation email ───────────────
    if (subscriberStatus !== 'already_active') {
      const emailResult = await sendConfirmationEmail(emailLower, optInToken, locale)
      if (!emailResult.success) {
        console.error('[leads/capture] confirmation email failed:', emailResult.error)
        // Non-fatal — subscriber is stored, email might arrive later
      }
    }

    // ── 4. Track referral if provided ──────────────────────────
    if (referral_code) {
      // Future: link this lead to the referring member in member_referrals (Phase 4)
      console.log('[leads/capture] referral_code received:', referral_code, 'for', emailLower)
    }

    // ── Response ───────────────────────────────────────────────
    return NextResponse.json({
      status: subscriberStatus === 'already_active' ? 'already_subscribed' : 'confirmation_sent',
      message:
        subscriberStatus === 'already_active'
          ? 'This email is already subscribed.'
          : 'Please check your email to confirm your subscription.',
    })
  } catch (error) {
    console.error('[leads/capture] unexpected error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 },
    )
  }
}
