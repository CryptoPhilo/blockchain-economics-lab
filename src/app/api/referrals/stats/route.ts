import { NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'

/**
 * OPS-011-T13: Get referral stats for the logged-in user
 *
 * GET /api/referrals/stats
 *
 * Returns:
 *   - referral_code
 *   - total_referrals, converted, rewarded, pending
 *   - recent referrals list (anonymized emails)
 */

function anonymizeEmail(email: string): string {
  const [local, domain] = email.split('@')
  if (!domain) return '***'
  const masked = local.length > 2
    ? local[0] + '***' + local[local.length - 1]
    : '***'
  return `${masked}@${domain}`
}

export async function GET() {
  try {
    const supabase = await createServerSupabaseClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    // Get user's referral code
    const { data: profile } = await supabase
      .from('profiles')
      .select('referral_code')
      .eq('id', user.id)
      .single()

    // Get stats
    const { data: referrals } = await supabase
      .from('member_referrals')
      .select('id, status, reward_type, reward_value, reward_granted_at, created_at, referred_id')
      .eq('referrer_id', user.id)
      .order('created_at', { ascending: false })

    const items = referrals || []
    const total = items.length
    const converted = items.filter(r => r.status === 'converted').length
    const rewarded = items.filter(r => r.status === 'rewarded').length
    const pending = items.filter(r => r.status === 'pending').length

    // Get referred user emails (anonymized) for recent list
    const referredIds = items.slice(0, 10).map(r => r.referred_id)
    let recentReferrals: Array<{ date: string; email: string; status: string }> = []

    if (referredIds.length > 0) {
      const { data: profiles } = await supabase
        .from('profiles')
        .select('id, email')
        .in('id', referredIds)

      const emailMap = new Map((profiles || []).map(p => [p.id, p.email]))

      recentReferrals = items.slice(0, 10).map(r => ({
        date: r.created_at,
        email: anonymizeEmail(emailMap.get(r.referred_id) || ''),
        status: r.status,
      }))
    }

    return NextResponse.json({
      referral_code: profile?.referral_code || '',
      stats: { total, converted, rewarded, pending },
      recent: recentReferrals,
    })
  } catch (error) {
    console.error('[referrals/stats] error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
