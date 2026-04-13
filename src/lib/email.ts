/**
 * Email sending utility via Resend API
 * OPS-001: Resend selected as email provider for Next.js/React ecosystem
 */

import { createHmac } from 'crypto'

const RESEND_API_KEY = process.env.RESEND_API_KEY || ''
const RESEND_API_URL = 'https://api.resend.com/emails'
const FROM_EMAIL = process.env.EMAIL_FROM || 'BCE Lab <research@bcelab.xyz>'
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'https://bcelab.xyz'
const UNSUBSCRIBE_SECRET = process.env.NEWSLETTER_API_SECRET || ''

interface SendEmailParams {
  to: string
  subject: string
  html: string
  text?: string
  tags?: { name: string; value: string }[]
}

interface SendEmailResult {
  success: boolean
  id?: string
  error?: string
}

export async function sendEmail(params: SendEmailParams): Promise<SendEmailResult> {
  if (!RESEND_API_KEY) {
    console.warn('[Email] RESEND_API_KEY not configured. Email not sent to:', params.to)
    // In development, log instead of failing
    return { success: true, id: 'dev-mode-no-send' }
  }

  try {
    const response = await fetch(RESEND_API_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: FROM_EMAIL,
        to: [params.to],
        subject: params.subject,
        html: params.html,
        text: params.text,
        tags: params.tags,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      console.error('[Email] Resend API error:', response.status, errorData)
      return { success: false, error: `Resend API error: ${response.status}` }
    }

    const data = await response.json()
    return { success: true, id: data.id }
  } catch (error) {
    console.error('[Email] Send failed:', error)
    return { success: false, error: String(error) }
  }
}

/**
 * Send subscription confirmation email (Double Opt-in)
 */
export async function sendConfirmationEmail(
  email: string,
  token: string,
  locale: string = 'en'
): Promise<SendEmailResult> {
  const confirmUrl = `${APP_URL}/api/subscribe?token=${token}`
  const isKo = locale === 'ko'

  const subject = isKo
    ? '[BCE Lab] 뉴스레터 구독을 확인해주세요'
    : '[BCE Lab] Confirm your newsletter subscription'

  const html = `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e5e7eb; padding: 40px 20px;">
  <div style="max-width: 560px; margin: 0 auto;">
    <div style="text-align: center; margin-bottom: 32px;">
      <div style="display: inline-block; width: 48px; height: 48px; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #9333ea); text-align: center; line-height: 48px; color: white; font-weight: bold; font-size: 20px;">B</div>
      <h1 style="color: white; font-size: 24px; margin: 16px 0 8px;">
        ${isKo ? '360° Project Intelligence' : '360° Project Intelligence'}
      </h1>
      <p style="color: #9ca3af; font-size: 14px; margin: 0;">
        Blockchain Economics Lab
      </p>
    </div>

    <div style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 32px; text-align: center;">
      <h2 style="color: white; font-size: 20px; margin: 0 0 16px;">
        ${isKo ? '구독을 확인해주세요' : 'Confirm Your Subscription'}
      </h2>
      <p style="color: #9ca3af; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">
        ${isKo
          ? '아래 버튼을 클릭하면 매주 Weekly Market Pulse와 Deep Dive Preview를 받으시게 됩니다.'
          : 'Click the button below to start receiving our Weekly Market Pulse and Deep Dive Preview.'}
      </p>
      <a href="${confirmUrl}" style="display: inline-block; padding: 14px 32px; background: #6366f1; color: white; text-decoration: none; border-radius: 12px; font-weight: 600; font-size: 16px;">
        ${isKo ? '구독 확인하기' : 'Confirm Subscription'}
      </a>
    </div>

    <div style="margin-top: 24px; padding: 16px; text-align: center;">
      <p style="color: #6b7280; font-size: 12px; margin: 0;">
        ${isKo
          ? '이 이메일을 요청하지 않으셨다면 무시하셔도 됩니다.'
          : "If you didn't request this email, you can safely ignore it."}
      </p>
    </div>

    <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center;">
      <p style="color: #4b5563; font-size: 11px; margin: 0;">
        © 2026 Blockchain Economics Lab · bcelab.xyz<br>
        This content is for informational purposes only. Not financial advice.
      </p>
    </div>
  </div>
</body>
</html>`

  return sendEmail({
    to: email,
    subject,
    html,
    tags: [
      { name: 'type', value: 'confirmation' },
      { name: 'locale', value: locale },
    ],
  })
}

/**
 * Send a newsletter to a single subscriber
 */
export async function sendNewsletter(
  email: string,
  subject: string,
  htmlContent: string,
  newsletterId: string,
  locale: string = 'en'
): Promise<SendEmailResult> {
  // STRIX-BL-003: Include HMAC token in unsubscribe URL for verification
  const unsubscribeToken = UNSUBSCRIBE_SECRET
    ? createHmac('sha256', UNSUBSCRIBE_SECRET).update(email.toLowerCase()).digest('hex')
    : ''
  const unsubscribeUrl = `${APP_URL}/api/subscribe/unsubscribe?email=${encodeURIComponent(email)}&token=${unsubscribeToken}`

  // Append unsubscribe footer
  const htmlWithFooter = htmlContent + `
    <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center;">
      <p style="color: #4b5563; font-size: 11px;">
        © 2026 Blockchain Economics Lab · bcelab.xyz<br>
        <a href="${unsubscribeUrl}" style="color: #6366f1; text-decoration: underline;">Unsubscribe</a>
      </p>
      <p style="color: #374151; font-size: 10px; margin-top: 8px;">
        This content is for informational and educational purposes only. Not financial advice.
      </p>
    </div>`

  return sendEmail({
    to: email,
    subject,
    html: htmlWithFooter,
    tags: [
      { name: 'type', value: 'newsletter' },
      { name: 'newsletter_id', value: newsletterId },
      { name: 'locale', value: locale },
    ],
  })
}
