import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'

const RESTRICTED_COUNTRIES = ['KR']

// Exchange referral URLs (will be replaced with real URLs after approval)
const EXCHANGE_URLS: Record<string, { referral: string; clean: string }> = {
  binance: {
    referral: 'https://www.binance.com/en/register?ref=BCELAB',
    clean: 'https://www.binance.com',
  },
  bybit: {
    referral: 'https://www.bybit.com/invite?ref=BCELAB',
    clean: 'https://www.bybit.com',
  },
  okx: {
    referral: 'https://www.okx.com/join/BCELAB',
    clean: 'https://www.okx.com',
  },
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl
  const exchange = searchParams.get('exchange')
  const source = searchParams.get('source') || 'web'
  const contentId = searchParams.get('content_id')

  if (!exchange || !EXCHANGE_URLS[exchange]) {
    return NextResponse.json({ error: 'Invalid exchange' }, { status: 400 })
  }

  // Geo-compliance check
  const country = request.headers.get('x-geo-country') ||
    request.headers.get('x-vercel-ip-country') ||
    ''
  const isRestricted = RESTRICTED_COUNTRIES.includes(country)

  // Log click event
  try {
    const supabase = await createServerSupabaseClient()
    await supabase.from('referral_clicks').insert({
      exchange,
      source,
      content_id: contentId || null,
      content_type: source === 'newsletter' ? 'newsletter' : source === 'report' ? 'report' : 'score_page',
      ip_country: country,
      geo_blocked: isRestricted,
    })
  } catch (e) {
    // Don't block redirect on logging failure
    console.error('Failed to log referral click:', e)
  }

  // Redirect: restricted countries get clean URL, others get referral URL
  const urls = EXCHANGE_URLS[exchange]
  const targetUrl = isRestricted ? urls.clean : urls.referral

  return NextResponse.redirect(targetUrl, { status: 302 })
}
