import { NextRequest, NextResponse } from 'next/server'
import { timingSafeEqual } from 'crypto'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { sendNewsletter } from '@/lib/email'

/**
 * POST /api/newsletter/send
 * Newsletter batch send worker.
 * Sends an approved newsletter to all opted-in subscribers.
 *
 * Body: { newsletter_id: string, api_secret: string }
 * Protected by API secret (not user auth — called by cron/admin).
 */

const API_SECRET = process.env.NEWSLETTER_API_SECRET
const BATCH_SIZE = 50 // Resend rate limit: 100/sec on Pro, stay safe at 50
const BATCH_DELAY_MS = 1100 // ~1 second between batches

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function verifyApiSecret(provided: string, secret: string): boolean {
  try {
    const providedBuf = Buffer.from(provided)
    const secretBuf = Buffer.from(secret)
    return timingSafeEqual(providedBuf, secretBuf)
  } catch {
    return false
  }
}

export async function POST(request: NextRequest) {
  try {
    // Check API secret is configured
    if (!API_SECRET) {
      return NextResponse.json({ error: 'Service Unavailable' }, { status: 503 })
    }

    const { newsletter_id, api_secret } = await request.json()

    // Auth check with timing-safe comparison
    if (!api_secret || !verifyApiSecret(api_secret, API_SECRET)) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    if (!newsletter_id) {
      return NextResponse.json({ error: 'newsletter_id is required' }, { status: 400 })
    }

    const supabase = await createServerSupabaseClient()

    // Fetch newsletter
    const { data: newsletter, error: nlError } = await supabase
      .from('newsletters')
      .select('*')
      .eq('id', newsletter_id)
      .single()

    if (nlError || !newsletter) {
      return NextResponse.json({ error: 'Newsletter not found' }, { status: 404 })
    }

    if (newsletter.status !== 'approved') {
      return NextResponse.json({
        error: `Newsletter status is "${newsletter.status}", must be "approved" to send`,
      }, { status: 400 })
    }

    // Mark as sending
    await supabase
      .from('newsletters')
      .update({ status: 'sending' })
      .eq('id', newsletter_id)

    // Fetch all opted-in, non-unsubscribed subscribers
    const { data: subscribers, error: subError } = await supabase
      .from('subscribers')
      .select('id, email, locale')
      .eq('opted_in', true)
      .eq('unsubscribed', false)

    if (subError || !subscribers) {
      await supabase
        .from('newsletters')
        .update({ status: 'approved' }) // revert
        .eq('id', newsletter_id)
      return NextResponse.json({ error: 'Failed to fetch subscribers' }, { status: 500 })
    }

    const totalRecipients = subscribers.length
    let sentCount = 0
    let failedCount = 0

    // Send in batches
    for (let i = 0; i < subscribers.length; i += BATCH_SIZE) {
      const batch = subscribers.slice(i, i + BATCH_SIZE)

      const results = await Promise.allSettled(
        batch.map(async (sub) => {
          const locale = sub.locale || 'en'
          const subject = locale === 'ko' && newsletter.title_ko
            ? newsletter.title_ko
            : newsletter.title_en

          const result = await sendNewsletter(
            sub.email,
            subject,
            newsletter.content_html || newsletter.content_md || '',
            newsletter_id,
            locale,
          )

          // Log delivery event
          if (result.success) {
            await supabase.from('newsletter_events').insert({
              newsletter_id,
              subscriber_id: sub.id,
              event_type: 'delivered',
              occurred_at: new Date().toISOString(),
            })
          }

          return result
        })
      )

      for (const r of results) {
        if (r.status === 'fulfilled' && r.value.success) {
          sentCount++
        } else {
          failedCount++
        }
      }

      // Rate limit: wait between batches
      if (i + BATCH_SIZE < subscribers.length) {
        await sleep(BATCH_DELAY_MS)
      }
    }

    // Mark as sent
    await supabase
      .from('newsletters')
      .update({
        status: 'sent',
        sent_at: new Date().toISOString(),
        total_recipients: sentCount,
      })
      .eq('id', newsletter_id)

    return NextResponse.json({
      status: 'sent',
      total_recipients: totalRecipients,
      sent: sentCount,
      failed: failedCount,
    })
  } catch (error) {
    console.error('[Newsletter] Send error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
