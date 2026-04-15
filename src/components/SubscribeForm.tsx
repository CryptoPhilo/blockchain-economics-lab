'use client'

import { useState, useTransition } from 'react'

/**
 * OPS-011-T02: Inline newsletter subscription form
 *
 * Renders an email input + submit button with live status feedback.
 * Posts to /api/leads/capture (OPS-011-T01) with source='newsletter'.
 *
 * Props:
 *  - locale: current UI language (for double opt-in email language)
 *  - source: lead source label (default 'homepage')
 *  - sourceId: optional content ID (report UUID, etc.)
 *  - className: additional wrapper classes
 *  - variant: 'default' (full CTA block) | 'compact' (input row only)
 */

interface SubscribeFormProps {
  locale: string
  source?: 'homepage' | 'newsletter' | 'lead_magnet' | 'rating_gate'
  sourceId?: string
  className?: string
  variant?: 'default' | 'compact'
  translations?: {
    placeholder?: string
    cta?: string
    sending?: string
    success?: string
    alreadySubscribed?: string
    error?: string
    checkEmail?: string
  }
}

type FormStatus = 'idle' | 'sending' | 'success' | 'already' | 'error'

const DEFAULT_TRANSLATIONS = {
  placeholder: 'Enter your email address',
  cta: 'Subscribe Free',
  sending: 'Subscribing…',
  success: 'Check your email to confirm!',
  alreadySubscribed: 'You\'re already subscribed!',
  error: 'Something went wrong. Please try again.',
  checkEmail: '📬 Confirmation email sent',
}

export default function SubscribeForm({
  locale,
  source = 'homepage',
  sourceId,
  className = '',
  variant = 'default',
  translations,
}: SubscribeFormProps) {
  const t = { ...DEFAULT_TRANSLATIONS, ...translations }
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<FormStatus>('idle')
  const [isPending, startTransition] = useTransition()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim() || isPending) return

    startTransition(async () => {
      setStatus('sending')
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

        if (res.status === 429) {
          setStatus('error')
          return
        }

        const data = await res.json()
        if (!res.ok) {
          setStatus('error')
          return
        }

        if (data.status === 'already_subscribed') {
          setStatus('already')
        } else {
          setStatus('success')
        }
      } catch {
        setStatus('error')
      }
    })
  }

  // ── Success / Already subscribed state ───────────────────────
  if (status === 'success' || status === 'already') {
    return (
      <div className={`text-center ${className}`}>
        <div className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-green-500/10 border border-green-500/20 text-green-400">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <span className="font-medium">
            {status === 'success' ? t.success : t.alreadySubscribed}
          </span>
        </div>
      </div>
    )
  }

  // ── Compact variant (e.g., footer, sidebar) ──────────────────
  if (variant === 'compact') {
    return (
      <form onSubmit={handleSubmit} className={`flex gap-2 ${className}`}>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => { setEmail(e.target.value); if (status === 'error') setStatus('idle') }}
          placeholder={t.placeholder}
          className="flex-1 px-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25 transition-colors"
          disabled={isPending}
        />
        <button
          type="submit"
          disabled={isPending}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white text-sm font-semibold rounded-lg transition-all whitespace-nowrap"
        >
          {status === 'sending' ? t.sending : t.cta}
        </button>
        {status === 'error' && (
          <p className="text-red-400 text-xs mt-1">{t.error}</p>
        )}
      </form>
    )
  }

  // ── Default variant (homepage hero / CTA block) ──────────────
  return (
    <div className={className}>
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-lg mx-auto">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => { setEmail(e.target.value); if (status === 'error') setStatus('idle') }}
          placeholder={t.placeholder}
          className="flex-1 px-5 py-3.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/25 transition-all"
          disabled={isPending}
        />
        <button
          type="submit"
          disabled={isPending}
          className="px-8 py-3.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 whitespace-nowrap"
        >
          {status === 'sending' ? t.sending : t.cta}
        </button>
      </form>
      {status === 'error' && (
        <p className="text-red-400 text-sm text-center mt-3">{t.error}</p>
      )}
    </div>
  )
}
