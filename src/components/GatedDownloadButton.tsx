'use client'

import { useState, useTransition } from 'react'

/**
 * OPS-011-T04: Gated report download button
 *
 * Wraps a PDF download link behind an email gate.
 * On first click, shows email input. After submission, reveals the download link.
 * Remembers unlocked state in sessionStorage.
 */

interface GatedDownloadButtonProps {
  reportId: string
  downloadUrl: string
  locale: string
  label: string
}

type Status = 'locked' | 'input' | 'submitting' | 'unlocked' | 'error'

export default function GatedDownloadButton({
  reportId,
  downloadUrl,
  locale,
  label,
}: GatedDownloadButtonProps) {
  const isKo = locale === 'ko'

  const [status, setStatus] = useState<Status>(() => {
    if (typeof window !== 'undefined') {
      try {
        if (sessionStorage.getItem('bce_dl_unlocked') === '1') return 'unlocked'
      } catch { /* */ }
    }
    return 'locked'
  })
  const [email, setEmail] = useState('')
  const [isPending, startTransition] = useTransition()

  function handleGateClick() {
    if (status === 'locked') {
      setStatus('input')
    }
  }

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
            source: 'lead_magnet',
            source_id: reportId,
            locale,
          }),
        })
        if (res.ok || res.status === 429) {
          setStatus('unlocked')
          try { sessionStorage.setItem('bce_dl_unlocked', '1') } catch { /* */ }
        } else {
          setStatus('error')
        }
      } catch {
        setStatus('error')
      }
    })
  }

  // ── Unlocked: show real download link ────────────────────────
  if (status === 'unlocked') {
    return (
      <a
        href={downloadUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="px-4 py-2 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 text-sm font-medium rounded-lg transition-colors shrink-0 border border-indigo-500/20"
      >
        📥 {label}
      </a>
    )
  }

  // ── Email input shown ────────────────────────────────────────
  if (status === 'input' || status === 'submitting' || status === 'error') {
    return (
      <div className="flex flex-col gap-1.5 shrink-0">
        <form onSubmit={handleSubmit} className="flex gap-1.5">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => { setEmail(e.target.value); if (status === 'error') setStatus('input') }}
            placeholder={isKo ? '이메일' : 'Email'}
            className="w-40 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 text-xs focus:outline-none focus:border-indigo-500/50"
            disabled={isPending}
            autoFocus
          />
          <button
            type="submit"
            disabled={isPending}
            className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white text-xs font-semibold rounded-lg transition-all whitespace-nowrap"
          >
            {status === 'submitting' ? '…' : '📥'}
          </button>
        </form>
        {status === 'error' && (
          <p className="text-red-400 text-[10px]">{isKo ? '다시 시도' : 'Try again'}</p>
        )}
      </div>
    )
  }

  // ── Locked: show gated button ────────────────────────────────
  return (
    <button
      onClick={handleGateClick}
      className="px-4 py-2 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 text-sm font-medium rounded-lg transition-colors shrink-0 border border-indigo-500/20 cursor-pointer"
    >
      📧 {isKo ? '이메일로 PDF 받기' : 'Get PDF (Free)'}
    </button>
  )
}
