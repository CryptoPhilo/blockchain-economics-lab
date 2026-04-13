import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { sendConfirmationEmail } from '@/lib/email'
import { randomBytes } from 'crypto'
import { subscribeLimiter, getRateLimitId, rateLimitResponse } from '@/lib/rate-limit'

export async function POST(request: NextRequest) {
  try {
    // STRIX-INFRA-002: Rate limit subscribe endpoint (5/hour per IP)
    const rlId = getRateLimitId(request)
    const rlResult = subscribeLimiter.check(rlId)
    if (!rlResult.success) {
      return rateLimitResponse(rlResult)
    }

    const { email, locale = 'en', source = 'website' } = await request.json()

    if (!email || !email.includes('@')) {
      return NextResponse.json({ error: 'Valid email is required' }, { status: 400 })
    }

    const supabase = await createServerSupabaseClient()
    const country = request.headers.get('x-geo-country') ||
      request.headers.get('x-vercel-ip-country') ||
      ''

    // Generate opt-in token for double opt-in
    const optInToken = randomBytes(32).toString('hex')

    // Check existing subscriber
    const { data: existing } = await supabase
      .from('subscribers')
      .select('id, opted_in, unsubscribed')
      .eq('email', email.toLowerCase())
      .single()

    if (existing) {
      if (existing.opted_in && !existing.unsubscribed) {
        return NextResponse.json({ status: 'already_subscribed' })
      }

      // Re-subscribe
      await supabase
        .from('subscribers')
        .update({
          opted_in: false,
          unsubscribed: false,
          opt_in_token: optInToken,
          opt_in_sent_at: new Date().toISOString(),
          locale,
          ip_country: country,
        })
        .eq('id', existing.id)
    } else {
      // New subscriber
      await supabase.from('subscribers').insert({
        email: email.toLowerCase(),
        locale,
        source,
        opted_in: false,
        opt_in_token: optInToken,
        opt_in_sent_at: new Date().toISOString(),
        ip_country: country,
      })
    }

    // Send confirmation email via Resend
    const emailResult = await sendConfirmationEmail(email.toLowerCase(), optInToken, locale)

    if (!emailResult.success) {
      console.error('Failed to send confirmation email:', emailResult.error)
      // Still return success to user — email might be delayed
    }

    return NextResponse.json({
      status: 'confirmation_sent',
      message: 'Please check your email to confirm subscription',
    })
  } catch (error) {
    console.error('Subscribe error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

// Confirm subscription (double opt-in)
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl
  const token = searchParams.get('token')

  if (!token) {
    return NextResponse.json({ error: 'Token required' }, { status: 400 })
  }

  try {
    const supabase = await createServerSupabaseClient()

    const { data: subscriber, error } = await supabase
      .from('subscribers')
      .update({
        opted_in: true,
        confirmed_at: new Date().toISOString(),
        opt_in_token: null,
      })
      .eq('opt_in_token', token)
      .select('id, locale')
      .single()

    if (error || !subscriber) {
      return NextResponse.json({ error: 'Invalid or expired token' }, { status: 400 })
    }

    // Redirect to success page
    const locale = subscriber.locale || 'en'
    return NextResponse.redirect(new URL(`/${locale}/subscribe?confirmed=true`, request.url))
  } catch (error) {
    console.error('Confirm error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
