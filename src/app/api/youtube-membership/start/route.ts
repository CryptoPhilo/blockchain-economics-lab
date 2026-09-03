import { NextRequest, NextResponse } from 'next/server'

import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { startYouTubeMembershipLink } from '@/lib/youtube-membership'

export async function POST(request: NextRequest) {
  try {
    const supabase = await createServerSupabaseClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()
    const channel = typeof body.channel === 'string' ? body.channel.trim() : ''
    if (!channel) {
      return NextResponse.json({ error: 'YouTube channel is required' }, { status: 400 })
    }

    const admin = createSupabaseAdminClient()
    const link = await startYouTubeMembershipLink(admin, user.id, channel)
    return NextResponse.json({ link })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Internal server error'
    console.error('[youtube-membership/start] error:', error)
    return NextResponse.json({ error: message }, { status: 400 })
  }
}
