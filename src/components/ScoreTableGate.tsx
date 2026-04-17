'use client'

import { useState, useTransition } from 'react'

/**
 * CMC-Style Market Cap Ranking Table with Email Gate
 *
 * Displays a CoinMarketCap-style ranking table with:
 * - Rank, Name/Symbol, Price, 24h Change, Market Cap, BCE Score, Report Badges
 * - Sorted by market cap
 * - Top N rows visible, rest behind email gate
 * - Responsive: hides some columns on mobile
 */

interface ScoreRow {
  rank: number
  name: string
  symbol: string
  slug: string
  price: number | null
  change24h: number | null
  marketCap: number
  score: number | null
  category: string
  reportTypes: string[]
  reportDates: {
    econ: string | null
    maturity: string | null
    forensic: string | null
  }
}

interface ScoreTableGateProps {
  rows: ScoreRow[]
  freeLimit?: number
  locale: string
}

type GateStatus = 'locked' | 'submitting' | 'unlocked' | 'error'

function formatPrice(value: number): string {
  if (value >= 1) {
    return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }
  if (value >= 0.01) {
    return `$${value.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`
  }
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 })}`
}

function formatMarketCap(value: number): string {
  if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
  if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`
  return `$${value.toFixed(0)}`
}

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

function isReportNew(reportDate: string | null): boolean {
  if (!reportDate) return false
  const sevenDaysAgo = new Date()
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
  const reportDateObj = new Date(reportDate)
  return reportDateObj > sevenDaysAgo
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
        {/* Rank */}
        <td className="py-3 px-3 text-center text-gray-500 text-sm font-mono w-12">
          {row.rank}
        </td>

        {/* Name + Symbol */}
        <td className="py-3 px-3">
          <div className="flex items-center gap-2">
            <div>
              <span className="font-semibold text-white text-sm">{row.name}</span>
              <span className="text-gray-500 text-xs ml-1.5">{row.symbol}</span>
            </div>
          </div>
        </td>

        {/* Price */}
        <td className="py-3 px-3 text-right text-sm text-white font-mono hidden sm:table-cell">
          {row.price != null ? formatPrice(row.price) : '-'}
        </td>

        {/* 24h Change */}
        <td className="py-3 px-3 text-right text-sm font-mono hidden sm:table-cell">
          {row.change24h != null ? (
            <span className={row.change24h >= 0 ? 'text-green-400' : 'text-red-400'}>
              {row.change24h >= 0 ? '+' : ''}{row.change24h.toFixed(2)}%
            </span>
          ) : (
            <span className="text-gray-600">-</span>
          )}
        </td>

        {/* Market Cap */}
        <td className="py-3 px-3 text-right text-sm text-white font-mono">
          {row.marketCap > 0 ? formatMarketCap(row.marketCap) : '-'}
        </td>

        {/* BCE Score */}
        <td className="py-3 px-3 text-right hidden md:table-cell">
          {row.score != null ? (
            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${getScoreColor(row.score)} ${getScoreBg(row.score)}`}>
              {row.score.toFixed(1)}
            </span>
          ) : (
            <span className="text-gray-600 text-xs">-</span>
          )}
        </td>

        {/* Report Badges */}
        <td className="py-3 px-3">
          <div className="flex gap-1 justify-end">
            {/* ECON Badge */}
            <div className="relative">
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  row.reportTypes.includes('econ')
                    ? 'bg-blue-500/15 text-blue-400 cursor-pointer hover:bg-blue-500/25'
                    : 'bg-gray-500/10 text-gray-600 cursor-not-allowed'
                }`}
              >
                ECON
              </span>
              {row.reportTypes.includes('econ') && isReportNew(row.reportDates.econ) && (
                <span className="absolute -top-1 -right-1 text-[8px] px-1 py-0.5 rounded bg-red-500 text-white font-bold">
                  New
                </span>
              )}
            </div>

            {/* MAT Badge */}
            <div className="relative">
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  row.reportTypes.includes('maturity')
                    ? 'bg-green-500/15 text-green-400 cursor-pointer hover:bg-green-500/25'
                    : 'bg-gray-500/10 text-gray-600 cursor-not-allowed'
                }`}
              >
                MAT
              </span>
              {row.reportTypes.includes('maturity') && isReportNew(row.reportDates.maturity) && (
                <span className="absolute -top-1 -right-1 text-[8px] px-1 py-0.5 rounded bg-red-500 text-white font-bold">
                  New
                </span>
              )}
            </div>

            {/* FOR Badge */}
            <div className="relative">
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  row.reportTypes.includes('forensic')
                    ? 'bg-red-500/15 text-red-400 cursor-pointer hover:bg-red-500/25'
                    : 'bg-gray-500/10 text-gray-600 cursor-not-allowed'
                }`}
              >
                FOR
              </span>
              {row.reportTypes.includes('forensic') && isReportNew(row.reportDates.forensic) && (
                <span className="absolute -top-1 -right-1 text-[8px] px-1 py-0.5 rounded bg-red-500 text-white font-bold">
                  New
                </span>
              )}
            </div>
          </div>
        </td>
      </tr>
    )
  }

  return (
    <div>
      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-white/5">
        <table className="w-full">
          <thead>
            <tr className="bg-white/[0.03] border-b border-white/10">
              <th className="py-3 px-3 text-center text-xs font-medium text-gray-500 uppercase w-12">
                #
              </th>
              <th className="py-3 px-3 text-left text-xs font-medium text-gray-500 uppercase">
                {isKo ? '종목' : 'Name'}
              </th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase hidden sm:table-cell">
                {isKo ? '가격' : 'Price'}
              </th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase hidden sm:table-cell">
                24h
              </th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase">
                {isKo ? '시가총액' : 'Market Cap'}
              </th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase hidden md:table-cell">
                BCE Score
              </th>
              <th className="py-3 px-3 text-right text-xs font-medium text-gray-500 uppercase">
                {isKo ? '보고서' : 'Reports'}
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
              {/* Blurred teaser rows */}
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
                    ? `+${gatedRows.length}개 프로젝트 랭킹 보기`
                    : `View ${gatedRows.length} more project rankings`}
                </h4>
                <p className="text-gray-400 text-sm mb-4">
                  {isKo
                    ? '이메일을 입력하면 전체 랭킹을 무료로 볼 수 있습니다'
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
