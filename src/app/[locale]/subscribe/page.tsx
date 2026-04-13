'use client'

import { useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { useSearchParams } from 'next/navigation'
import DisclaimerBanner from '@/components/DisclaimerBanner'

export default function SubscribePage() {
  const locale = useLocale()
  const searchParams = useSearchParams()
  const confirmed = searchParams.get('confirmed') === 'true'

  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'sent' | 'error' | 'already'>(
    confirmed ? 'sent' : 'idle'
  )

  const isKo = locale === 'ko'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus('loading')

    try {
      const res = await fetch('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, locale, source: 'website' }),
      })
      const data = await res.json()
      if (data.status === 'already_subscribed') {
        setStatus('already')
      } else if (data.status === 'confirmation_sent') {
        setStatus('sent')
      } else {
        setStatus('error')
      }
    } catch {
      setStatus('error')
    }
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-6 py-20">
      <div className="max-w-lg w-full">
        {/* Success state */}
        {(status === 'sent' || confirmed) && (
          <div className="text-center">
            <div className="w-20 h-20 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-6">
              <span className="text-4xl">✅</span>
            </div>
            <h1 className="text-3xl font-bold text-white mb-4">
              {confirmed
                ? (isKo ? '구독이 확인되었습니다!' : 'Subscription Confirmed!')
                : (isKo ? '확인 이메일을 보냈습니다' : 'Check Your Email')}
            </h1>
            <p className="text-gray-400 mb-8">
              {confirmed
                ? (isKo
                  ? '매주 월요일 Weekly Market Pulse와 목요일 Deep Dive Preview를 받으시게 됩니다.'
                  : 'You\'ll receive our Weekly Market Pulse every Monday and Deep Dive Preview every Thursday.')
                : (isKo
                  ? '이메일의 확인 링크를 클릭하여 구독을 완료해주세요.'
                  : 'Please click the confirmation link in your email to complete your subscription.')}
            </p>
          </div>
        )}

        {/* Form state */}
        {status !== 'sent' && !confirmed && (
          <>
            <div className="text-center mb-10">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm mb-6">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                {isKo ? '무료 뉴스레터' : 'Free Newsletter'}
              </div>

              <h1 className="text-4xl font-bold text-white mb-4">
                {isKo ? '360° 프로젝트 인텔리전스' : '360° Project Intelligence'}
              </h1>
              <p className="text-gray-400 leading-relaxed">
                {isKo
                  ? '매주 AI 기반 암호화폐 리서치를 무료로 받아보세요. 토큰노믹스 분석, 성숙도 평가, 포렌식 리스크 경보를 한 곳에서.'
                  : 'Get weekly AI-powered crypto research delivered free. Tokenomics analysis, maturity assessments, and forensic risk alerts — all in one place.'}
              </p>
            </div>

            {/* What you get */}
            <div className="space-y-4 mb-8">
              {[
                {
                  icon: '📊',
                  title: isKo ? 'Weekly Market Pulse (매주 월요일)' : 'Weekly Market Pulse (Every Monday)',
                  desc: isKo ? '주간 시장 요약 + 추적 프로젝트 업데이트 + 포렌식 레이더' : 'Market overview + tracked project updates + forensic radar',
                },
                {
                  icon: '🔍',
                  title: isKo ? 'Deep Dive Preview (매주 목요일)' : 'Deep Dive Preview (Every Thursday)',
                  desc: isKo ? '최신 보고서 프리뷰 + 핵심 발견 + 데이터 테이블' : 'Latest report preview + key findings + data tables',
                },
                {
                  icon: '🚨',
                  title: isKo ? 'Forensic Alert (이벤트 시)' : 'Forensic Alerts (Event-driven)',
                  desc: isKo ? '실시간 리스크 경보 — 가격 급변, 고래 이동, 이상 징후' : 'Real-time risk alerts — price spikes, whale moves, anomalies',
                },
              ].map((item) => (
                <div key={item.icon} className="flex items-start gap-4 p-4 rounded-xl bg-white/5 border border-white/5">
                  <span className="text-2xl">{item.icon}</span>
                  <div>
                    <h3 className="font-semibold text-white text-sm">{item.title}</h3>
                    <p className="text-xs text-gray-500 mt-1">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={isKo ? '이메일 주소를 입력하세요' : 'Enter your email address'}
                required
                className="w-full px-5 py-3.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <button
                type="submit"
                disabled={status === 'loading'}
                className="w-full px-5 py-3.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/25"
              >
                {status === 'loading'
                  ? (isKo ? '처리 중...' : 'Subscribing...')
                  : (isKo ? '무료 구독하기' : 'Subscribe for Free')}
              </button>
            </form>

            {status === 'already' && (
              <p className="text-center text-yellow-400 text-sm mt-4">
                {isKo ? '이미 구독 중입니다.' : 'You\'re already subscribed!'}
              </p>
            )}
            {status === 'error' && (
              <p className="text-center text-red-400 text-sm mt-4">
                {isKo ? '오류가 발생했습니다. 다시 시도해주세요.' : 'Something went wrong. Please try again.'}
              </p>
            )}

            {/* Trust signals */}
            <div className="flex justify-center gap-6 mt-6 text-xs text-gray-600">
              <span>🔒 {isKo ? 'GDPR 준수' : 'GDPR Compliant'}</span>
              <span>📧 {isKo ? '주 2회' : '2x Weekly'}</span>
              <span>❌ {isKo ? '스팸 없음' : 'No Spam'}</span>
            </div>
          </>
        )}

        <div className="mt-10">
          <DisclaimerBanner compact />
        </div>
      </div>
    </div>
  )
}
