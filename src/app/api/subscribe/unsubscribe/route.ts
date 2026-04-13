import { NextRequest, NextResponse } from 'next/server'
import { createHmac, timingSafeEqual } from 'crypto'
import { createServerSupabaseClient } from '@/lib/supabase-server'

/**
 * GET /api/subscribe/unsubscribe?email=...&token=...
 * One-click unsubscribe handler (linked from newsletter footer).
 * Marks subscriber as unsubscribed and redirects to confirmation page.
 * Protected by HMAC-SHA256 token verification.
 */

const UNSUBSCRIBE_SECRET = process.env.NEWSLETTER_API_SECRET || ''

// STRIX-AUTH-002: Use timing-safe comparison for HMAC token verification
function verifyUnsubscribeToken(email: string, token: string): boolean {
  if (!UNSUBSCRIBE_SECRET) {
    return false
  }
  const expected = createHmac('sha256', UNSUBSCRIBE_SECRET)
    .update(email.toLowerCase())
    .digest('hex')
  try {
    const expectedBuf = Buffer.from(expected)
    const tokenBuf = Buffer.from(token)
    return expectedBuf.length === tokenBuf.length && timingSafeEqual(expectedBuf, tokenBuf)
  } catch {
    return false
  }
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl
  const email = searchParams.get('email')
  const token = searchParams.get('token')

  if (!email) {
    return NextResponse.json({ error: 'Email required' }, { status: 400 })
  }

  if (!token || !verifyUnsubscribeToken(email, token)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  try {
    const supabase = await createServerSupabaseClient()

    const { data: subscriber, error } = await supabase
      .from('subscribers')
      .update({
        unsubscribed: true,
        unsubscribed_at: new Date().toISOString(),
      })
      .eq('email', email.toLowerCase())
      .select('id, locale')
      .single()

    if (error || !subscriber) {
      // Don't reveal if email exists or not — just show generic page
      return new NextResponse(
        `<!DOCTYPE html><html><body style="background:#0a0a0f;color:#e5e7eb;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
          <div style="text-align:center;">
            <h1 style="color:white;">Unsubscribed</h1>
            <p>You have been unsubscribed from BCE Lab newsletters.</p>
          </div>
        </body></html>`,
        { headers: { 'Content-Type': 'text/html' } }
      )
    }

    const locale = subscriber.locale || 'en'
    return NextResponse.redirect(
      new URL(`/${locale}/subscribe?unsubscribed=true`, request.url)
    )
  } catch (error) {
    console.error('[Unsubscribe] Error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
