'use client'

import { useState, useTransition } from 'react'

/**
 * OPS-011-T04: Lead Magnet Email Gate
 *
 * Wraps gated content (e.g., report download link, executive summary)
 * behind an email collection form. Once the user submits their email,
 * the gated content is revealed and the lead is captured.
 *
 * Uses localStorage to remember unlocked state per-browser.
 */

interface LeadMagnetGateProps {
  /** Unique ID for this gated content (used as localStorage key) */
  gateId: string
  /** Content source ID for analytics (e.g., report UUID) */
  sourceId?: string
  /** Lead source label */
  source?: 'lead_magnet' | 'rating_gate'
  /** Current locale */
  locale: string
  /** Teaser content shown before email submission */
  teaser: React.ReactNode
  /** Gated content revealed after email submission */
  children: React.ReactNode
  /** Optional: visual variant */
  variant?: 'inline' | 'overlay'
}

type GateStatus = 'locked' | 'submitting' | 'unlocked' | 'error'

export default function LeadMagnetGate({
  gateId,
  sourceId,
  source = 'lead_magnet',
  locale,
  teaser,
  children,
  variant = 'inline',
}: LeadMagnetGateProps) {
  // Check if already unlocked in this session
  const [status, setStatus] = useState<GateStatus>(() => {
    if (typeof window !== 'undefined') {
      try {
        const unlocked = sessionStorage.getItem(`bce_gate_${gateId}`)
        if (unlocked === '1') return 'unlocked'
      } catch { /* SSR or private browsing */ }
    }
    return 'locked'
  })
  const [email, setEmail] = useState('')
  const [isPending, startTransition] = useTransition()

  const isKo = locale === 'ko'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim() || isPending) return

    startTransition(async () => {
      setStatus('submitting')
      try {
        const res = await fetch('/api/leads/capture', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: email.trim(),
            source,
            source_id: sourceId,
            locale,
          }),
        })

        if (res.ok || res.status === 429) {
          // Unlock even on rate limit — user already showed intent
          setStatus('unlocked')
          try {
            sessionStorage.setItem(`bce_gate_${gateId}`, '1')
          } catch { /* private browsing */ }
        } else {
          setStatus('error')
        }
      } catch {
        setStatus('error')
      }
    })
  }

  if (status === 'unlocked') {
    return <>{children}</>
  }

  // ── Overlay variant (for blurred content sections) ───────────
  if (variant === 'overlay') {
    return (
      <div className="relative">
        {/* Blurred teaser */}
        <div className="select-none pointer-events-none" style={{ filter: 'blur(6px)', opacity: 0.5 }}>
          {teaser}
        </div>

        {/* Overlay form */}
        <div className="absolute inset-0 flex items-center justify-center bg-gray-950/60 backdrop-blur-sm rounded-xl">
          <div className="text-center max-w-sm mx-4">
            <div className="w-12 h-12 rounded-full bg-indigo-500/20 flex items-center justify-center mx-auto mb-3">
              <span className="text-xl">📧</span>
            </div>
            <h4 className="text-white font-semibold mb-2">
              {isKo ? '이메일을 입력하면 전체 내용을 볼 수 있습니다' : 'Enter your email to unlock full content'}
            </h4>
            <form onSubmit={handleSubmit} className="flex flex-col gap-2">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => { setEmail(e.target.value); if (status === 'error') setStatus('locked') }}
                placeholder={isKo ? '이메일 주소' : 'Email address'}
                className="px-4 py-2.5 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 text-sm focus:outline-none focus:border-indigo-500/50"
                disabled={isPending}
              />
              <button
                type="submit"
                disabled={isPending}
                className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white text-sm font-semibold rounded-lg transition-all"
              >
                {status === 'submitting'
                  ? (isKo ? '처리 중…' : 'Unlocking…')
                  : (isKo ? '무료로 잠금 해제' : 'Unlock Free')}
              </button>
              {status === 'error' && (
                <p className="text-red-400 text-xs">{isKo ? '오류가 발생했습니다.' : 'Something went wrong.'}</p>
              )}
            </form>
            <p className="text-gray-500 text-[11px] mt-2">
              {isKo ? '무료 뉴스레터 구독 포함. 언제든 해지 가능.' : 'Includes free newsletter. Unsubscribe anytime.'}
            </p>
          </div>
        </div>
      </div>
    )
  }

  // ── Inline variant (replaces download button) ────────────────
  return (
    <div>
      {teaser}
      <div className="mt-3 p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/15">
        <p className="text-sm text-gray-400 mb-2">
          {isKo ? '📧 이메일을 입력하면 다운로드 링크가 활성화됩니다' : '📧 Enter your email to unlock the download'}
        </p>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => { setEmail(e.target.value); if (status === 'error') setStatus('locked') }}
            placeholder={isKo ? '이메일 주소' : 'Email address'}
            className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500/50"
            disabled={isPending}
          />
          <button
            type="submit"
            disabled={isPending}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white text-sm font-semibold rounded-lg transition-all whitespace-nowrap"
          >
            {status === 'submitting' ? '…' : (isKo ? '잠금 해제' : 'Unlock')}
          </button>
        </form>
        {status === 'error' && (
          <p className="text-red-400 text-xs mt-1">{isKo ? '다시 시도해주세요.' : 'Please try again.'}</p>
        )}
      </div>
    </div>
  )
}
