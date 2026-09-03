import { redirect } from 'next/navigation'

import YouTubeMembershipManager from '@/components/YouTubeMembershipManager'
import { createServerSupabaseClient } from '@/lib/supabase-server'

interface MembershipPageProps {
  params: Promise<{ locale: string }>
}

export default async function MembershipPage({ params }: MembershipPageProps) {
  const { locale } = await params
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect(`/${locale}/auth`)
  }

  return <YouTubeMembershipManager locale={locale} />
}
