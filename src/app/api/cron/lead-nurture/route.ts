import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { sendEmail } from '@/lib/email'

/**
 * OPS-011-T09: Lead → Signup Nurture Automation
 *
 * Cron endpoint that sends automated nurture emails to subscribers
 * who haven't signed up for an account yet.
 *
 * Schedule: Daily at 10:00 KST (01:00 UTC)
 * Trigger: Vercel Cron or external scheduler
 *
 * Sequence:
 *   Day 2:  "무료 회원 혜택 안내"
 *   Day 5:  "이번 주 등급 변동 Top 5"
 *   Day 7:  "무료 가입하고 대시보드 시작하기"
 *   Day 14: "놓치고 있는 3가지 기능"
 */

const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'https://bcelab.xyz'
const CRON_SECRET = process.env.CRON_SECRET || ''

// Day offsets for the nurture sequence
const NURTURE_DAYS = [2, 5, 7, 14] as const

interface NurtureTemplate {
  subject: Record<string, string>
  heading: Record<string, string>
  body: Record<string, string>
  cta: Record<string, string>
}

const TEMPLATES: Record<number, NurtureTemplate> = {
  2: {
    subject: {
      en: '[BCE Lab] Unlock exclusive member benefits — free',
      ko: '[BCE Lab] 무료 회원 혜택을 확인하세요',
    },
    heading: {
      en: 'Did you know? Free members get more',
      ko: '알고 계셨나요? 무료 회원 혜택이 있습니다',
    },
    body: {
      en: 'As a newsletter subscriber, you\'re already getting great research. But free members unlock full maturity rankings, unlimited Executive Summaries, a personal dashboard, and a 20% first-purchase discount.',
      ko: '뉴스레터 구독자로서 이미 좋은 리서치를 받고 계십니다. 하지만 무료 회원이 되시면 전체 등급표, 무제한 Executive Summary, 개인 대시보드, 첫 구매 20% 할인까지 이용하실 수 있습니다.',
    },
    cta: {
      en: 'Create Free Account',
      ko: '무료 가입하기',
    },
  },
  5: {
    subject: {
      en: '[BCE Lab] This week\'s maturity score changes',
      ko: '[BCE Lab] 이번 주 성숙도 점수 변동 현황',
    },
    heading: {
      en: 'Maturity Score Movers This Week',
      ko: '이번 주 성숙도 점수 변동',
    },
    body: {
      en: 'Projects are constantly evolving. Sign up to track score changes in real-time on your dashboard, and set alerts for the projects you care about.',
      ko: '프로젝트는 끊임없이 변화합니다. 가입하시면 대시보드에서 실시간 점수 변동을 추적하고, 관심 프로젝트의 알림을 설정할 수 있습니다.',
    },
    cta: {
      en: 'View Full Rankings',
      ko: '전체 등급표 보기',
    },
  },
  7: {
    subject: {
      en: '[BCE Lab] Your personal research dashboard awaits',
      ko: '[BCE Lab] 개인 리서치 대시보드가 준비되어 있습니다',
    },
    heading: {
      en: 'Your Dashboard is Ready',
      ko: '대시보드가 준비되어 있습니다',
    },
    body: {
      en: 'It takes less than a minute to create your free account. You\'ll get a personal dashboard with portfolio tracking, saved reports, and referral rewards. Plus, your first purchase comes with 20% off.',
      ko: '1분이면 무료 계정을 만들 수 있습니다. 포트폴리오 추적, 저장된 보고서, 추천 리워드가 포함된 개인 대시보드를 이용하세요. 첫 구매 시 20% 할인도 제공됩니다.',
    },
    cta: {
      en: 'Sign Up Free — 1 Minute',
      ko: '무료 가입 — 1분이면 완료',
    },
  },
  14: {
    subject: {
      en: '[BCE Lab] 3 features you\'re missing out on',
      ko: '[BCE Lab] 놓치고 있는 3가지 기능',
    },
    heading: {
      en: "Here's What You're Missing",
      ko: '이런 기능을 놓치고 계십니다',
    },
    body: {
      en: '1. Full maturity score table with 7-axis breakdown\n2. Executive Summary downloads for every published report\n3. Personal referral code with rewards for every friend who signs up\n\nAll free. No credit card required.',
      ko: '1. 7축 상세 분석이 포함된 전체 성숙도 등급표\n2. 모든 발행 보고서의 Executive Summary 다운로드\n3. 친구 가입 시 리워드가 적립되는 추천 코드\n\n모두 무료입니다. 신용카드가 필요하지 않습니다.',
    },
    cta: {
      en: 'Get Started — It\'s Free',
      ko: '시작하기 — 무료입니다',
    },
  },
}

function buildNurtureEmail(day: number, locale: string): { subject: string; html: string } {
  const tmpl = TEMPLATES[day]
  const lang = tmpl.subject[locale] ? locale : 'en'
  const subject = tmpl.subject[lang]
  const heading = tmpl.heading[lang]
  const body = tmpl.body[lang].replace(/\n/g, '<br>')
  const cta = tmpl.cta[lang]
  const signupUrl = `${APP_URL}/${locale}/auth`

  const html = `
<!DOCTYPE html>
<html lang="${locale}">
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', sans-serif; background: #0a0a0f; color: #e5e7eb; padding: 40px 20px;">
  <div style="max-width: 560px; margin: 0 auto;">
    <div style="text-align: center; margin-bottom: 24px;">
      <div style="display: inline-block; width: 40px; height: 40px; border-radius: 10px; background: linear-gradient(135deg, #6366f1, #9333ea); text-align: center; line-height: 40px; color: white; font-weight: bold; font-size: 18px;">B</div>
    </div>

    <div style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 32px;">
      <h2 style="color: white; font-size: 20px; margin: 0 0 16px; text-align: center;">
        ${heading}
      </h2>
      <p style="color: #9ca3af; font-size: 14px; line-height: 1.7; margin: 0 0 24px;">
        ${body}
      </p>
      <div style="text-align: center;">
        <a href="${signupUrl}" style="display: inline-block; padding: 14px 32px; background: #6366f1; color: white; text-decoration: none; border-radius: 12px; font-weight: 600; font-size: 15px;">
          ${cta}
        </a>
      </div>
    </div>

    <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center;">
      <p style="color: #4b5563; font-size: 11px; margin: 0;">
        © 2026 Blockchain Economics Lab · bcelab.xyz
      </p>
    </div>
  </div>
</body>
</html>`

  return { subject, html }
}

export async function GET(request: NextRequest) {
  // Verify cron secret
  const authHeader = request.headers.get('authorization')
  if (CRON_SECRET && authHeader !== `Bearer ${CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const supabase = await createServerSupabaseClient()
    const now = new Date()
    let totalSent = 0
    const errors: string[] = []

    for (const day of NURTURE_DAYS) {
      // Find subscribers who:
      // 1. opted_in = true (confirmed)
      // 2. signed up exactly `day` days ago (±12 hours)
      // 3. do NOT have a corresponding profiles row (haven't created an account)
      const targetDate = new Date(now)
      targetDate.setDate(targetDate.getDate() - day)
      const windowStart = new Date(targetDate)
      windowStart.setHours(windowStart.getHours() - 12)
      const windowEnd = new Date(targetDate)
      windowEnd.setHours(windowEnd.getHours() + 12)

      const { data: leads } = await supabase
        .from('subscribers')
        .select('id, email, locale')
        .eq('opted_in', true)
        .eq('unsubscribed', false)
        .gte('confirmed_at', windowStart.toISOString())
        .lte('confirmed_at', windowEnd.toISOString())

      if (!leads || leads.length === 0) continue

      // Filter out those who already have an account
      const emails = leads.map((l) => l.email)
      const { data: existingProfiles } = await supabase
        .from('profiles')
        .select('email')
        .in('email', emails)

      const profileEmails = new Set((existingProfiles || []).map((p) => p.email))
      const nurturableLeads = leads.filter((l) => !profileEmails.has(l.email))

      // Send nurture emails
      for (const lead of nurturableLeads) {
        const locale = lead.locale || 'en'
        const { subject, html } = buildNurtureEmail(day, locale)

        const result = await sendEmail({
          to: lead.email,
          subject,
          html,
          tags: [
            { name: 'type', value: 'nurture' },
            { name: 'nurture_day', value: String(day) },
            { name: 'locale', value: locale },
          ],
        })

        if (result.success) {
          totalSent++
        } else {
          errors.push(`${lead.email}: ${result.error}`)
        }
      }
    }

    return NextResponse.json({
      status: 'ok',
      sent: totalSent,
      errors: errors.length,
      errorDetails: errors.slice(0, 10),
      timestamp: now.toISOString(),
    })
  } catch (error) {
    console.error('[lead-nurture] cron error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
