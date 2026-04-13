import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'

/**
 * POST /api/webhooks/resend
 * Resend webhook handler for tracking email delivery events.
 * Resend sends events: email.sent, email.delivered, email.opened,
 * email.clicked, email.bounced, email.complained, email.unsubscribed
 *
 * Configure at: https://resend.com/webhooks
 * Webhook URL: https://bcelab.xyz/api/webhooks/resend
 */

const RESEND_WEBHOOK_SECRET = process.env.RESEND_WEBHOOK_SECRET || ''

// Map Resend event types to our internal types
const EVENT_TYPE_MAP: Record<string, string> = {
  'email.delivered': 'delivered',
  'email.opened': 'opened',
  'email.clicked': 'clicked',
  'email.bounced': 'bounced',
  'email.complained': 'unsubscribed',
}

interface ResendWebhookPayload {
  type: string
  created_at: string
  data: {
    email_id: string
    from: string
    to: string[]
    subject: string
    created_at: string
    tags?: { name: string; value: string }[]
  }
}

export async function POST(request: NextRequest) {
  try {
    // STRIX-BL-002: Full svix webhook signature verification
    const body = await request.text()
    const svixId = request.headers.get('svix-id')
    const svixTimestamp = request.headers.get('svix-timestamp')
    const svixSignature = request.headers.get('svix-signature')

    if (!svixId || !svixTimestamp || !svixSignature) {
      console.warn('[Resend Webhook] Missing svix headers')
      return NextResponse.json({ error: 'Missing webhook signature' }, { status: 401 })
    }

    if (RESEND_WEBHOOK_SECRET) {
      // Verify svix signature using HMAC-SHA256
      // svix signs: `${svixId}.${svixTimestamp}.${body}` with base64-decoded secret
      const { createHmac } = await import('crypto')
      try {
        // Svix secret is prefixed with "whsec_" and base64 encoded
        const secretStr = RESEND_WEBHOOK_SECRET.startsWith('whsec_')
          ? RESEND_WEBHOOK_SECRET.substring(6)
          : RESEND_WEBHOOK_SECRET
        const secretBytes = Buffer.from(secretStr, 'base64')

        const toSign = `${svixId}.${svixTimestamp}.${body}`
        const expectedSig = createHmac('sha256', secretBytes)
          .update(toSign)
          .digest('base64')

        // svix-signature header format: "v1,<base64sig>" (may contain multiple)
        const signatures = svixSignature.split(' ')
        const verified = signatures.some((sig) => {
          const parts = sig.split(',')
          return parts.length === 2 && parts[1] === expectedSig
        })

        if (!verified) {
          console.warn('[Resend Webhook] Invalid svix signature')
          return NextResponse.json({ error: 'Invalid webhook signature' }, { status: 401 })
        }

        // Verify timestamp is within 5 minutes to prevent replay attacks
        const timestampSec = parseInt(svixTimestamp, 10)
        const nowSec = Math.floor(Date.now() / 1000)
        if (Math.abs(nowSec - timestampSec) > 300) {
          console.warn('[Resend Webhook] Timestamp too old/new')
          return NextResponse.json({ error: 'Webhook timestamp expired' }, { status: 401 })
        }
      } catch (verifyError) {
        console.error('[Resend Webhook] Signature verification error:', verifyError)
        return NextResponse.json({ error: 'Signature verification failed' }, { status: 401 })
      }
    } else {
      console.warn('[Resend Webhook] RESEND_WEBHOOK_SECRET not configured — skipping verification')
    }

    const payload: ResendWebhookPayload = JSON.parse(body)
    const { type, data } = payload

    // Only process event types we care about
    const internalEventType = EVENT_TYPE_MAP[type]
    if (!internalEventType) {
      // Acknowledge but ignore (e.g., email.sent is redundant with our own logging)
      return NextResponse.json({ received: true })
    }

    const supabase = await createServerSupabaseClient()
    const recipientEmail = data.to?.[0]?.toLowerCase()

    if (!recipientEmail) {
      return NextResponse.json({ received: true })
    }

    // Extract newsletter_id from tags
    const newsletterTag = data.tags?.find((t) => t.name === 'newsletter_id')
    const newsletterId = newsletterTag?.value

    // Find subscriber by email
    const { data: subscriber } = await supabase
      .from('subscribers')
      .select('id')
      .eq('email', recipientEmail)
      .single()

    if (!subscriber) {
      // Not a known subscriber — might be a transactional email
      return NextResponse.json({ received: true })
    }

    // Handle bounce — mark subscriber for cleanup
    if (internalEventType === 'bounced') {
      await supabase
        .from('subscribers')
        .update({
          unsubscribed: true,
          unsubscribed_at: new Date().toISOString(),
        })
        .eq('id', subscriber.id)
    }

    // Log the event if we have a newsletter_id
    if (newsletterId) {
      await supabase.from('newsletter_events').insert({
        newsletter_id: newsletterId,
        subscriber_id: subscriber.id,
        event_type: internalEventType,
        metadata: {
          resend_email_id: data.email_id,
          subject: data.subject,
        },
        occurred_at: payload.created_at || new Date().toISOString(),
      })
    }

    return NextResponse.json({ received: true })
  } catch (error) {
    console.error('[Resend Webhook] Error:', error)
    // Always return 200 to prevent Resend retries on our errors
    return NextResponse.json({ received: true, error: 'Processing error' })
  }
}
