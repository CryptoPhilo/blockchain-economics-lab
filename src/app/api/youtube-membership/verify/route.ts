import { NextResponse } from 'next/server'

import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { verifyYouTubeMembershipLink } from '@/lib/youtube-membership'

export async function POST() {
  try {
    const supabase = await createServerSupabaseClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const admin = createSupabaseAdminClient()
    const link = await verifyYouTubeMembershipLink(admin, user.id)
    return NextResponse.json({ link, active: link.status === 'active' })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Internal server error'
    console.error('[youtube-membership/verify] error:', error)
    return NextResponse.json({ error: message }, { status: 400 })
  }
}
