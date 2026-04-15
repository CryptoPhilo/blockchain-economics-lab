'use client'

import { useState, useTransition } from 'react'

/**
 * OPS-011-T05: Score Table Email Gate
 *
 * Renders a maturity score rankings table. The top N rows are visible;
 * remaining rows are blurred behind an email gate.
 *
 * Once the user submits their email, all rows are revealed.
 */

interface ScoreRow {
  rank: number
  name: string
  symbol: string
  score: number
  category?: string
}

interface ScoreTableGateProps {
  rows: ScoreRow[]
  freeLimit?: number  // default 20
  locale: string
}

type GateStatus = 'locked' | 'submitting' | 'unlocked' | 'error'

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-400'
  if (score >= 60) return 'text-yellow-400'
  if (score >= 40) return 'text-orange-400'
  return 'text-red-400'
}

function getScoreBg(score: number): string {
  if (score >= 80) return 'bg-green-500/10'
  if (score >= 60) return 'bg-yellow-500/10'
  if (score >= 40) return 'bg-orange-500/10'
  return 'bg-red-500/10'
}

export default function ScoreTableGate({
  rows,
  freeLimit = 20,
  locale,
}: ScoreTableGateProps) {
  const isKo = locale === 'ko'

  const [status, setStatus] = useState<GateStatus>(() => {
    if (typeof window !== 'undefined') {
      try {
        if (sessionStorage.getItem('bce_score_unlocked') === '1') return 'unlocked'
      } catch { /* */ }
    }
    return 'locked'
  })
  const [email, setEmail] = useState('')
  const [isPending, startTransition] = useTransition()

  const freeRows = rows.slice(0, freeLimit)
  const gatedRows = rows.slice(freeLimit)
  const isLocked = status !== 'unlocked' && gatedRows.length > 0

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
            source: 'rating_gate',
            locale,
          }),
        })
        if (res.ok || res.status === 429) {
          setStatus('unlocked')
          try { sessionStorage.setItem('bce_score_unlocked', '1') } catch { /* */ }
        } else {
          setStatus('error')
        }
      } catch {
        setStatus('error')
      }
    })
  }

  function renderRow(row: ScoreRow, blurred = false) {
    return (
      <tr
        key={row.rank}
        className={`border-b border-white/5 ${blurred ? 'select-none' : 'hover:bg-white/[0.02]'}`}
        style={blurred ? { filter: 'blur(5px)', pointerEvents: 'none' } : undefined}
      >
        <td className="py-3 px-4 text-center text-gray-500 text-sm font-mono">{row.rank}</td>
        <td className="py-3 px-4">
          <span className="font-semibold text-white">{row.name}</span>
          <span className="text-gray-500 text-sm ml-2">{row.symbol}</span>
        </td>
        {row.category && (
          <td className="py-3 px-4 text-sm text-gray-500 hidden md:table-cell">{row.category}</td>
        )}
        <td className="py-3 px-4 text-right">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-sm font-bold ${getScoreColor(row.score)} ${getScoreBg(row.score)}`}>
            {row.score.toFixed(1)}
          </span>
        </td>
      </tr>
    )
  }

  const hasCategory = rows.some((r) => r.category)

  return (
    <div>
      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-white/5">
        <table className="w-full">
          <thead>
            <tr className="bg-white/[0.03] border-b border-white/10">
              <th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase w-16">#</th>
              <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase">
                {isKo ? '프로젝트' : 'Project'}
              </th>
              {hasCategory && (
                <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase hidden md:table-cell">
                  {isKo ? '카테고리' : 'Category'}
                </th>
              )}
              <th className="py-3 px-4 text-right text-xs font-medium text-gray-500 uppercase w-28">
                BCE Score
              </th>
            </tr>
          </thead>
          <tbody>
            {freeRows.map((row) => renderRow(row))}
          </tbody>
        </table>
      </div>

      {/* Gate section for remaining rows */}
      {gatedRows.length > 0 && (
        <div className="relative mt-0">
          {isLocked ? (
            <>
              {/* Show a few blurred rows as teaser */}
              <div className="overflow-hidden rounded-b-xl border-x border-b border-white/5">
                <table className="w-full">
                  <tbody>
                    {gatedRows.slice(0, 5).map((row) => renderRow(row, true))}
                  </tbody>
                </table>
              </div>

              {/* Email gate overlay */}
              <div className="mt-4 p-6 rounded-xl bg-gradient-to-r from-indigo-500/5 to-purple-500/5 border border-indigo-500/15 text-center">
                <h4 className="text-white font-semibold mb-1">
                  {isKo
                    ? `+${gatedRows.length}개 프로젝트 점수 보기`
                    : `View ${gatedRows.length} more project scores`}
                </h4>
                <p className="text-gray-400 text-sm mb-4">
                  {isKo
                    ? '이메일을 입력하면 전체 등급표를 무료로 볼 수 있습니다'
                    : 'Enter your email to unlock the full ranking table for free'}
                </p>
                <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2 max-w-md mx-auto">
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); if (status === 'error') setStatus('locked') }}
                    placeholder={isKo ? '이메일 주소' : 'Email address'}
                    className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500/50"
                    disabled={isPending}
                  />
                  <button
                    type="submit"
                    disabled={isPending}
                    className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white text-sm font-semibold rounded-lg transition-all whitespace-nowrap"
                  >
                    {status === 'submitting'
                      ? (isKo ? '처리 중…' : 'Unlocking…')
                      : (isKo ? '전체 보기 (무료)' : 'Unlock All (Free)')}
                  </button>
                </form>
                {status === 'error' && (
                  <p className="text-red-400 text-xs mt-2">{isKo ? '오류가 발생했습니다.' : 'Something went wrong.'}</p>
                )}
                <p className="text-gray-600 text-[11px] mt-3">
                  {isKo ? '무료 뉴스레터 포함. 언제든 해지 가능.' : 'Includes free newsletter. Unsubscribe anytime.'}
                </p>
              </div>
            </>
          ) : (
            /* Unlocked: show all remaining rows */
            <div className="overflow-hidden rounded-b-xl border-x border-b border-white/5">
              <table className="w-full">
                <tbody>
                  {gatedRows.map((row) => renderRow(row))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
