'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, Loader2, RefreshCw, Video } from 'lucide-react'

import type { YouTubeMembershipLink } from '@/lib/youtube-membership'

const BCELAB_YOUTUBE_JOIN_URL =
  process.env.NEXT_PUBLIC_BCELAB_YOUTUBE_JOIN_URL || 'https://www.youtube.com/@BCELAB/join'

interface YouTubeMembershipManagerProps {
  locale: string
}

interface StatusPayload {
  configured: boolean
  linked: boolean
  active: boolean
  link: YouTubeMembershipLink | null
  error?: string
}

export default function YouTubeMembershipManager({ locale }: YouTubeMembershipManagerProps) {
  const isKo = locale === 'ko'
  const [status, setStatus] = useState<StatusPayload | null>(null)
  const [channel, setChannel] = useState('')
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadStatus() {
    const response = await fetch('/api/youtube-membership/status')
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.error || 'Could not load membership status')
    setStatus(payload)
  }

  useEffect(() => {
    // Initial membership state must come from the authenticated API session.
    loadStatus()
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load membership status'))
      .finally(() => setLoading(false))
  }, [])

  async function runAction(action: 'start' | 'verify' | 'refresh') {
    setActionLoading(true)
    setError('')
    setMessage('')

    try {
      const response = await fetch(`/api/youtube-membership/${action}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: action === 'start' ? JSON.stringify({ channel }) : undefined,
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'Membership check failed')
      await loadStatus()
      setMessage(isKo ? '멤버십 상태를 갱신했습니다.' : 'Membership status updated.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Membership check failed')
    } finally {
      setActionLoading(false)
    }
  }

  const link = status?.link
  const isActive = Boolean(status?.active)

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <div className="mb-8">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-red-300">
          YouTube Membership
        </p>
        <h1 className="mt-3 text-3xl font-bold text-white">
          {isKo ? 'BCELAB 슬라이드 열람 인증' : 'BCELAB Slide Access Verification'}
        </h1>
        <p className="mt-3 text-sm leading-6 text-gray-400">
          {isKo
            ? 'BCELAB 유튜브 채널 유료 가입자만 보고서 HTML 슬라이드를 열람할 수 있습니다. 먼저 유튜브 채널 멤버십에 가입한 뒤 이 페이지에서 인증하세요.'
            : 'Only paid members of the BCELAB YouTube channel can view HTML report slides. Join the channel on YouTube first, then verify your membership here.'}
        </p>
        <a
          href={BCELAB_YOUTUBE_JOIN_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-5 inline-flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-red-500"
        >
          <Video className="h-4 w-4" aria-hidden="true" />
          {isKo ? 'BCELAB 유튜브 유료 가입 페이지 열기' : 'Open BCELAB YouTube join page'}
        </a>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
        {loading ? (
          <div className="flex items-center gap-3 text-gray-300">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            <span>{isKo ? '상태 확인 중' : 'Checking status'}</span>
          </div>
        ) : (
          <div className="space-y-6">
            {status && !status.configured && (
              <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4 text-sm text-yellow-100">
                {isKo
                  ? '서버에 YouTube 멤버십 API 설정이 필요합니다.'
                  : 'YouTube membership API credentials must be configured on the server.'}
              </div>
            )}

            <div className="flex flex-col gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-base font-semibold text-white">
                  {isActive ? (isKo ? '인증 완료' : 'Verified') : (isKo ? '인증 필요' : 'Verification required')}
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  {link?.youtube_channel_title || link?.youtube_channel_id || (isKo ? '연결된 채널 없음' : 'No linked channel')}
                </p>
              </div>
              <span className={`inline-flex w-fit items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-semibold ${
                isActive
                  ? 'border-green-400/30 bg-green-500/10 text-green-200'
                  : 'border-red-400/30 bg-red-500/10 text-red-200'
              }`}>
                {isActive ? <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> : <Video className="h-4 w-4" aria-hidden="true" />}
                {isActive ? (isKo ? '유료 멤버' : 'Paid member') : (isKo ? '미인증' : 'Not verified')}
              </span>
            </div>

            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault()
                void runAction('start')
              }}
            >
              <label className="block text-sm font-semibold text-gray-300" htmlFor="youtube-channel">
                {isKo ? '내 YouTube 채널 URL 또는 @handle' : 'Your YouTube channel URL or @handle'}
              </label>
              <div className="flex flex-col gap-3 sm:flex-row">
                <input
                  id="youtube-channel"
                  type="text"
                  value={channel}
                  onChange={(event) => setChannel(event.target.value)}
                  placeholder={isKo ? '@handle 또는 https://www.youtube.com/channel/UC...' : '@handle or https://www.youtube.com/channel/UC...'}
                  className="min-h-11 flex-1 rounded-lg border border-white/10 bg-black/20 px-4 text-sm text-white placeholder:text-gray-600 focus:border-red-300/50 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={actionLoading || !channel.trim()}
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Video className="h-4 w-4" aria-hidden="true" />
                  {isKo ? '채널 연결' : 'Link channel'}
                </button>
              </div>
            </form>

            {link && (
              <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                <p className="text-sm font-semibold text-white">
                  {isKo ? '채널 설명에 넣을 인증 코드' : 'Verification code for your channel description'}
                </p>
                <code className="mt-3 block w-fit rounded-md border border-white/10 bg-black/40 px-3 py-2 text-sm font-semibold text-red-100">
                  {link.verification_code}
                </code>
                <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                  <button
                    type="button"
                    onClick={() => void runAction('verify')}
                    disabled={actionLoading}
                    className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-white px-4 text-sm font-semibold text-slate-950 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {actionLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
                    {isKo ? '코드 확인 및 멤버십 검사' : 'Verify code and membership'}
                  </button>
                  <button
                    type="button"
                    onClick={() => void runAction('refresh')}
                    disabled={actionLoading}
                    className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-white/10 px-4 text-sm font-semibold text-gray-300 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                    {isKo ? '멤버십 재확인' : 'Refresh membership'}
                  </button>
                </div>
              </div>
            )}

            {(message || error || link?.last_error) && (
              <p className={`text-sm ${error || link?.last_error ? 'text-red-300' : 'text-green-300'}`}>
                {error || link?.last_error || message}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
