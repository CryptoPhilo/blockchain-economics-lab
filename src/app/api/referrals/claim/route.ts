import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'

/**
 * OPS-011-T13: Claim a referral code during/after signup
 *
 * POST /api/referrals/claim
 * Body: { referral_code: string }
 *
 * Called automatically when a new user signs up with a referral code,
 * or manually from the dashboard if they enter one later.
 *
 * Flow:
 *   1. Validate referral_code exists in profiles
 *   2. Ensure user isn't referring themselves
 *   3. Ensure user hasn't already been referred
 *   4. Create member_referrals record
 *   5. Update referred user's profile.referred_by
 */

export async function POST(request: NextRequest) {
  try {
    const supabase = await createServerSupabaseClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()
    const code = (body.referral_code || '').trim().toUpperCase()

    if (!code) {
      return NextResponse.json({ error: 'Referral code is required' }, { status: 400 })
    }

    // 1. Find referrer by code
    const { data: referrer } = await supabase
      .from('profiles')
      .select('id, referral_code')
      .eq('referral_code', code)
      .single()

    if (!referrer) {
      return NextResponse.json({ error: 'Invalid referral code' }, { status: 404 })
    }

    // 2. Can't refer yourself
    if (referrer.id === user.id) {
      return NextResponse.json({ error: 'Cannot use your own referral code' }, { status: 400 })
    }

    // 3. Check if already referred
    const { data: existing } = await supabase
      .from('member_referrals')
      .select('id')
      .eq('referred_id', user.id)
      .maybeSingle()

    if (existing) {
      return NextResponse.json({ error: 'Already referred by someone' }, { status: 409 })
    }

    // 4. Create referral record
    const { error: insertErr } = await supabase
      .from('member_referrals')
      .insert({
        referrer_id: referrer.id,
        referred_id: user.id,
        referral_code: code,
        status: 'converted',
        reward_type: 'discount',
        reward_value: 20,  // 20% discount for referrer on next purchase
      })

    if (insertErr) {
      console.error('[referrals/claim] insert error:', insertErr)
      return NextResponse.json({ error: 'Failed to process referral' }, { status: 500 })
    }

    // 5. Update referred user's profile
    await supabase
      .from('profiles')
      .update({ referred_by: referrer.id, updated_at: new Date().toISOString() })
      .eq('id', user.id)

    return NextResponse.json({
      success: true,
      message: 'Referral claimed successfully',
      referrer_code: code,
    })
  } catch (error) {
    console.error('[referrals/claim] error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
