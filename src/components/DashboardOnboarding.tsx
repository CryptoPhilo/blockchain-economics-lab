'use client'

import { useState } from 'react'
import OnboardingModal from './OnboardingModal'

/**
 * OPS-011-T08: Dashboard onboarding wrapper
 *
 * Rendered by the dashboard server component when the user
 * hasn't completed onboarding. Shows the modal, then hides it
 * when onComplete fires.
 */

interface DashboardOnboardingProps {
  userId: string
  referralCode: string
  locale: string
}

export default function DashboardOnboarding({ userId, referralCode, locale }: DashboardOnboardingProps) {
  const [show, setShow] = useState(true)

  if (!show) return null

  return (
    <OnboardingModal
      userId={userId}
      referralCode={referralCode}
      locale={locale}
      onComplete={() => setShow(false)}
    />
  )
}
