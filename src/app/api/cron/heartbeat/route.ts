import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

export const dynamic = 'force-dynamic'

const CRON_SECRET = process.env.CRON_SECRET || ''

function isAuthorized(request: NextRequest) {
  if (!CRON_SECRET) return true
  return request.headers.get('authorization') === `Bearer ${CRON_SECRET}`
}

export async function GET(request: NextRequest) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const checks: Record<string, unknown> = {
    app: 'ok',
    supabaseConfig: Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY),
  }

  let status = 200

  if (checks.supabaseConfig) {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      { auth: { persistSession: false } },
    )

    const { error } = await supabase
      .from('project_reports')
      .select('id')
      .limit(1)

    checks.projectReportsQuery = error ? { ok: false, message: error.message } : { ok: true }
    if (error) status = 503
  } else {
    status = 503
  }

  return NextResponse.json({
    status: status === 200 ? 'ok' : 'degraded',
    checkedAt: new Date().toISOString(),
    checks,
  }, { status })
}
