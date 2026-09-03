import { NextResponse } from 'next/server'

import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import {
  getUserYouTubeMembershipLink,
  hasActiveYouTubeMembership,
  isYouTubeMembershipConfigured,
} from '@/lib/youtube-membership'

export async function GET() {
  try {
    const supabase = await createServerSupabaseClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const admin = createSupabaseAdminClient()
    const link = await getUserYouTubeMembershipLink(admin, user.id)
    return NextResponse.json({
      configured: isYouTubeMembershipConfigured(),
      linked: Boolean(link),
      active: hasActiveYouTubeMembership(link),
      link,
    })
  } catch (error) {
    console.error('[youtube-membership/status] error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
