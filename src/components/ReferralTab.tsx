'use client'

import { useState, useEffect, useCallback } from 'react'

/**
 * OPS-011-T13: Dashboard "My Referrals" tab
 *
 * Shows referral code, share link, stats, and recent referral list.
 * Fetches data from /api/referrals/stats.
 */

interface ReferralStats {
  referral_code: string
  stats: { total: number; converted: number; rewarded: number; pending: number }
  recent: Array<{ date: string; email: string; status: string }>
}

interface ReferralTabProps {
  locale: string
  referralCode: string
}

export default function ReferralTab({ locale, referralCode }: ReferralTabProps) {
  const isKo = locale === 'ko'
  const [data, setData] = useState<ReferralStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState<'code' | 'link' | null>(null)

  const shareUrl = typeof window !== 'undefined'
    ? `${window.location.origin}/${locale}/auth?ref=${referralCode}`
    : `https://bcelab.xyz/${locale}/auth?ref=${referralCode}`

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch('/api/referrals/stats')
      if (res.ok) {
        setData(await res.json())
      }
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStats()
  }, [fetchStats])

  function copyToClipboard(text: string, type: 'code' | 'link') {
    navigator.clipboard.writeText(text)
    setCopied(type)
    setTimeout(() => setCopied(null), 2000)
  }

  const stats = data?.stats || { total: 0, converted: 0, rewarded: 0, pending: 0 }

  return (
    <div className="space-y-6">
      {/* Referral Code + Share */}
      <div className="p-6 rounded-xl bg-gradient-to-br from-indigo-500/10 to-purple-500/5 border border-indigo-500/20">
        <h3 className="font-semibold text-white mb-1">
          {isKo ? '내 추천 코드' : 'My Referral Code'}
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          {isKo
            ? '친구에게 공유하면 가입 시 양쪽 모두 혜택을 받습니다'
            : 'Share with friends — both of you get rewards when they sign up'}
        </p>

        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 px-4 py-3 bg-black/30 rounded-lg font-mono text-xl text-indigo-400 tracking-wider text-center">
            {referralCode}
          </div>
          <button
            onClick={() => copyToClipboard(referralCode, 'code')}
            className="px-4 py-3 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {copied === 'code' ? (isKo ? '복사됨!' : 'Copied!') : (isKo ? '복사' : 'Copy')}
          </button>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            readOnly
            value={shareUrl}
            className="flex-1 px-3 py-2 bg-black/20 text-gray-400 text-xs rounded-lg border border-white/5"
          />
          <button
            onClick={() => copyToClipboard(shareUrl, 'link')}
            className="px-3 py-2 bg-white/5 hover:bg-white/10 text-gray-300 text-xs rounded-lg border border-white/10 transition-colors"
          >
            {copied === 'link' ? '✓' : (isKo ? '링크 복사' : 'Copy Link')}
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: isKo ? '총 추천' : 'Total', value: stats.total, color: 'text-white' },
          { label: isKo ? '전환됨' : 'Converted', value: stats.converted, color: 'text-green-400' },
          { label: isKo ? '보상 완료' : 'Rewarded', value: stats.rewarded, color: 'text-indigo-400' },
          { label: isKo ? '대기 중' : 'Pending', value: stats.pending, color: 'text-yellow-400' },
        ].map((s) => (
          <div key={s.label} className="p-4 rounded-xl bg-white/[0.03] border border-white/5 text-center">
            <p className={`text-2xl font-bold ${s.color}`}>{loading ? '-' : s.value}</p>
            <p className="text-xs text-gray-500 mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Reward Info */}
      <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
        <h4 className="font-medium text-white text-sm mb-2">
          {isKo ? '추천 리워드 안내' : 'Referral Rewards'}
        </h4>
        <div className="space-y-2 text-sm text-gray-400">
          <div className="flex items-start gap-2">
            <span className="text-green-400 mt-0.5">●</span>
            <span>{isKo ? '친구가 가입하면 → 추천인에게 다음 구매 20% 할인' : 'Friend signs up → you get 20% off next purchase'}</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-indigo-400 mt-0.5">●</span>
            <span>{isKo ? '친구가 유료 구매하면 → 추천인에게 무료 보고서 1건 지급' : 'Friend makes a purchase → you get 1 free report'}</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-yellow-400 mt-0.5">●</span>
            <span>{isKo ? '피추천인도 첫 구매 20% 할인 혜택' : 'Your friend also gets 20% off their first purchase'}</span>
          </div>
        </div>
      </div>

      {/* Recent Referrals */}
      {!loading && data && data.recent.length > 0 && (
        <div>
          <h4 className="font-medium text-white text-sm mb-3">
            {isKo ? '최근 추천 현황' : 'Recent Referrals'}
          </h4>
          <div className="space-y-2">
            {data.recent.map((r, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/[0.02]">
                <span className="text-sm text-gray-400">{r.email}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500">
                    {new Date(r.date).toLocaleDateString()}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    r.status === 'rewarded' ? 'bg-indigo-500/20 text-indigo-400' :
                    r.status === 'converted' ? 'bg-green-500/20 text-green-400' :
                    'bg-yellow-500/20 text-yellow-400'
                  }`}>
                    {r.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && stats.total === 0 && (
        <p className="text-center text-gray-500 text-sm py-4">
          {isKo ? '아직 추천 내역이 없습니다. 위의 코드를 공유해보세요!' : 'No referrals yet. Share your code above to get started!'}
        </p>
      )}
    </div>
  )
}
