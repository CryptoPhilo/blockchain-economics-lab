'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import type { ScoreRow } from '@/lib/score-row'

/**
 * CMC-Style Market Cap Ranking Table with Email Gate
 *
 * Displays a CoinMarketCap-style ranking table with:
 * - Rank, Name/Symbol, 24h Change, Market Cap, BCE Score, Report Badges
 * - Sorted by market cap
 * - Top N rows visible, rest behind email gate
 * - Responsive: hides some columns on mobile
 */

export type { ScoreRow }

interface ScoreTableGateProps {
  rows: ScoreRow[]
  freeLimit?: number
  locale: string
  className?: string
  currentPage?: number
  totalPages?: number
  rowsPerPage?: number
  getDetailHref?: (row: ScoreRow) => string
  nameTitle?: (row: ScoreRow, isKo: boolean) => string
}

type GateStatus = 'locked' | 'submitting' | 'unlocked' | 'error'

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

function CmcRankBadge({ rank }: { rank: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center rounded border border-white/10 bg-white/[0.04] px-1 py-0.5 text-[9px] font-semibold leading-none text-slate-400 sm:px-1.5 sm:text-[10px]"
      title={`CoinMarketCap #${rank}`}
    >
      CMC #{rank}
    </span>
  )
}

export default function ScoreTableGate({
  rows,
  freeLimit = 20,
  locale,
  className,
  currentPage = 1,
  totalPages = 1,
  rowsPerPage = 100,
  getDetailHref,
  nameTitle,
}: ScoreTableGateProps) {
  const isKo = locale === 'ko'
  const router = useRouter()

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
    const detailHref = getDetailHref ? getDetailHref(row) : `/${locale}/projects/${row.slug}`
    const handleRowClick = blurred
      ? undefined
      : (e: React.MouseEvent<HTMLTableRowElement>) => {
          // Respect modifier keys (cmd/ctrl/shift/alt) so users can open in a new tab via the inner <a>.
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
          // If the click already landed on an interactive element (anchor/button/input), let it handle.
          const target = e.target as HTMLElement
          if (target.closest('a, button, input')) return
          router.push(detailHref)
        }
    return (
      <tr
        key={`${row.slug}-${row.rank ?? 'unranked'}`}
        onClick={handleRowClick}
        className={`border-b border-white/5 ${blurred ? 'select-none' : 'hover:bg-white/[0.05] transition-colors duration-150 cursor-pointer'}`}
        style={blurred ? { filter: 'blur(5px)', pointerEvents: 'none' } : undefined}
      >
        {/* Rank */}
        <td className="py-2.5 px-2 sm:px-3 text-center text-gray-500 text-xs font-mono w-10 sm:w-12">
          {row.rank ?? '-'}
        </td>

        {/* Name + Symbol */}
        <td className="py-2.5 pl-3 sm:pl-4 pr-2 sm:pr-3 align-top">
          <div className="flex items-start gap-2">
            {blurred ? (
              <div className="min-w-0">
                <div className="flex min-w-0 items-center gap-1.5">
                  <span className="truncate font-semibold text-white text-sm leading-tight">{row.name}</span>
                  {row.cmcRank ? <CmcRankBadge rank={row.cmcRank} /> : null}
                </div>
                <div className="mt-0.5 flex items-center gap-2">
                  <div className="text-gray-500 text-[11px] font-medium uppercase leading-tight truncate">{row.symbol}</div>
                  <div className="text-[10px] font-mono text-slate-500 sm:hidden whitespace-nowrap">
                    {row.marketCap > 0 ? formatMarketCap(row.marketCap) : '-'}
                  </div>
                  {row.score != null ? (
                    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold sm:hidden ${getScoreColor(row.score)} ${getScoreBg(row.score)}`}>
                      {row.score.toFixed(1)}
                    </span>
                  ) : null}
                </div>
              </div>
            ) : (
              <Link
                href={detailHref}
                className="group inline-block min-w-0 max-w-[10.5rem] sm:max-w-none"
                title={nameTitle ? nameTitle(row, isKo) : (isKo ? `${row.name} 상세 페이지` : `${row.name} project page`)}
              >
                <div className="flex min-w-0 items-center gap-1.5">
                  <span className="truncate font-semibold text-white text-sm leading-tight group-hover:text-indigo-400 group-hover:underline transition-colors">
                    {row.name}
                  </span>
                  {row.cmcRank ? <CmcRankBadge rank={row.cmcRank} /> : null}
                </div>
                <div className="mt-0.5 flex items-center gap-2">
                  <div className="text-gray-500 text-[11px] font-medium uppercase leading-tight truncate">{row.symbol}</div>
                  <div className="text-[10px] font-mono text-slate-500 sm:hidden whitespace-nowrap">
                    {row.marketCap > 0 ? formatMarketCap(row.marketCap) : '-'}
                  </div>
                  {row.score != null ? (
                    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold sm:hidden ${getScoreColor(row.score)} ${getScoreBg(row.score)}`}>
                      {row.score.toFixed(1)}
                    </span>
                  ) : null}
                </div>
              </Link>
            )}
          </div>
        </td>

        {/* Market Cap */}
        <td className="hidden py-2.5 px-2 sm:px-3 text-right text-xs sm:text-sm text-white font-mono whitespace-nowrap sm:table-cell">
          {row.marketCap > 0 ? formatMarketCap(row.marketCap) : '-'}
        </td>

        {/* 24h Change */}
        <td className="py-2.5 px-2 sm:px-3 text-right text-xs sm:text-sm font-mono hidden sm:table-cell whitespace-nowrap">
          {row.change24h != null ? (
            <span className={row.change24h >= 0 ? 'text-green-400' : 'text-red-400'}>
              {row.change24h >= 0 ? '+' : ''}{row.change24h.toFixed(2)}%
            </span>
          ) : (
            <span className="text-gray-600">-</span>
          )}
        </td>

        {/* BCE Score */}
        <td className="py-2.5 px-2 sm:px-3 text-right hidden md:table-cell">
          {row.score != null ? (
            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${getScoreColor(row.score)} ${getScoreBg(row.score)}`}>
              {row.score.toFixed(1)}
            </span>
          ) : (
            <span className="text-gray-600 text-xs">-</span>
          )}
        </td>

        {/* Report Status Badges (read-only — navigate via project name) */}
        <td className="py-2.5 px-2 sm:px-3 align-top w-[6.25rem] sm:w-auto">
          <div className="grid grid-cols-2 justify-items-end gap-1 sm:flex sm:min-w-[7.25rem] sm:flex-wrap sm:justify-end sm:gap-x-1 sm:gap-y-1">
            {/* ECON Badge */}
            <div className="relative">
              {row.reportTypes.includes('econ') ? (
                <span
                  className="inline-flex items-center text-[9px] px-1 py-0.5 rounded font-medium bg-blue-500/15 text-blue-400 whitespace-nowrap sm:text-[10px] sm:px-1.5"
                  title={isKo ? 'ECON 보고서 발행됨' : 'ECON report published'}
                >
                  ECON
                </span>
              ) : (
                <span
                  className="inline-flex items-center text-[9px] px-1 py-0.5 rounded font-medium bg-gray-500/10 text-gray-600 whitespace-nowrap sm:text-[10px] sm:px-1.5"
                  title={isKo ? 'ECON 보고서 미발행' : 'ECON report not published'}
                >
                  ECON
                </span>
              )}
              {row.reportTypes.includes('econ') && isReportNew(row.reportDates.econ) && (
                <span className="absolute -top-1 -right-1 text-[7px] leading-none px-[3px] py-0.5 rounded bg-black/80 border border-red-500 text-red-500 font-bold shadow-lg whitespace-nowrap sm:text-[8px] sm:px-1">
                  New
                </span>
              )}
            </div>

            {/* MAT Badge */}
            <div className="relative">
              {row.reportTypes.includes('maturity') ? (
                <span
                  className="inline-flex items-center text-[9px] px-1 py-0.5 rounded font-medium bg-green-500/15 text-green-400 whitespace-nowrap sm:text-[10px] sm:px-1.5"
                  title={isKo ? 'MAT 보고서 발행됨' : 'MAT report published'}
                >
                  MAT
                </span>
              ) : (
                <span
                  className="inline-flex items-center text-[9px] px-1 py-0.5 rounded font-medium bg-gray-500/10 text-gray-600 whitespace-nowrap sm:text-[10px] sm:px-1.5"
                  title={isKo ? 'MAT 보고서 미발행' : 'MAT report not published'}
                >
                  MAT
                </span>
              )}
              {row.reportTypes.includes('maturity') && isReportNew(row.reportDates.maturity) && (
                <span className="absolute -top-1 -right-1 text-[8px] leading-none px-1 py-0.5 rounded bg-black/80 border border-red-500 text-red-500 font-bold shadow-lg whitespace-nowrap">
                  New
                </span>
              )}
            </div>

            {/* FOR Badge */}
            <div className="relative">
              {row.reportTypes.includes('forensic') ? (
                <span
                  className="inline-flex items-center text-[9px] px-1 py-0.5 rounded font-medium bg-red-500/15 text-red-400 whitespace-nowrap sm:text-[10px] sm:px-1.5"
                  title={isKo ? 'FOR 보고서 발행됨' : 'FOR report published'}
                >
                  FOR
                </span>
              ) : (
                <span
                  className="inline-flex items-center text-[9px] px-1 py-0.5 rounded font-medium bg-gray-500/10 text-gray-600 whitespace-nowrap sm:text-[10px] sm:px-1.5"
                  title={isKo ? 'FOR 보고서 미발행' : 'FOR report not published'}
                >
                  FOR
                </span>
              )}
              {row.reportTypes.includes('forensic') && isReportNew(row.reportDates.forensic) && (
                <span className="absolute -top-1 -right-1 text-[8px] leading-none px-1 py-0.5 rounded bg-black/80 border border-red-500 text-red-500 font-bold shadow-lg whitespace-nowrap">
                  New
                </span>
              )}
            </div>
          </div>
        </td>
      </tr>
    )
  }

  function formatPageRange(page: number) {
    const start = (page - 1) * rowsPerPage + 1
    const end = page * rowsPerPage
    return isKo ? `${start}-${end}위` : `${start}-${end}`
  }

  return (
    <div className={className}>
      {/* Table */}
      <div className="rounded-xl border border-white/5">
        <table className="w-full table-fixed sm:table-auto">
          <thead>
            <tr className="bg-white/[0.08] border-b border-white/20 sticky top-0 z-10">
              <th className="py-2.5 px-2 sm:px-3 text-center text-[11px] font-medium text-gray-500 uppercase w-10 sm:w-12">
                #
              </th>
              <th className="py-2.5 pl-3 sm:pl-4 pr-2 sm:pr-3 text-left text-[11px] font-medium text-gray-500 uppercase">
                {isKo ? '종목' : 'Name'}
              </th>
              <th className="hidden py-2.5 px-2 sm:px-3 text-right text-[11px] font-medium text-gray-500 uppercase sm:table-cell">
                {isKo ? '시가총액' : 'Market Cap'}
              </th>
              <th className="py-2.5 px-2 sm:px-3 text-right text-[11px] font-medium text-gray-500 uppercase hidden sm:table-cell">
                24h
              </th>
              <th className="py-2.5 px-2 sm:px-3 text-right text-[11px] font-medium text-gray-500 uppercase hidden md:table-cell">
                BCE Score
              </th>
              <th className="py-2.5 px-2 sm:px-3 text-right text-[11px] font-medium text-gray-500 uppercase w-[6.25rem] sm:w-auto">
                {isKo ? '리포트' : 'Reports'}
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
              <div className="overflow-visible rounded-b-xl border-x border-b border-white/5">
                <table className="w-full table-fixed sm:table-auto">
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
            <div className="overflow-visible rounded-b-xl border-x border-b border-white/5">
              <table className="w-full table-fixed sm:table-auto">
                <tbody>
                  {gatedRows.map((row) => renderRow(row))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {totalPages > 1 && (
        <nav className="flex flex-wrap items-center justify-center gap-2 sm:gap-4 mt-8 pb-1">
          {currentPage > 1 && (
            <Link
              href={`/${locale}/score?page=${currentPage - 1}`}
              className="px-4 sm:px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white text-sm font-medium transition-colors whitespace-nowrap"
            >
              ← {isKo ? `이전 (${formatPageRange(currentPage - 1)})` : `Previous (${formatPageRange(currentPage - 1)})`}
            </Link>
          )}
          <div className="flex flex-wrap justify-center gap-2">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <Link
                key={page}
                href={`/${locale}/score?page=${page}`}
                className={`px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  page === currentPage
                    ? 'bg-indigo-500 text-white'
                    : 'bg-white/5 hover:bg-white/10 text-gray-400'
                }`}
              >
                {formatPageRange(page)}
              </Link>
            ))}
          </div>
          {currentPage < totalPages && (
            <Link
              href={`/${locale}/score?page=${currentPage + 1}`}
              className="px-4 sm:px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white text-sm font-medium transition-colors whitespace-nowrap"
            >
              {isKo ? `다음 (${formatPageRange(currentPage + 1)})` : `Next (${formatPageRange(currentPage + 1)})`} →
            </Link>
          )}
        </nav>
      )}
    </div>
  )
}
