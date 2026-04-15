'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase-client'

/**
 * OPS-011-T08: Post-signup onboarding modal
 *
 * Shown on first dashboard visit when onboarding_completed = false.
 * Collects interests, shows referral code, marks onboarding done.
 */

interface OnboardingModalProps {
  userId: string
  referralCode: string
  locale: string
  onComplete: () => void
}

const INTEREST_OPTIONS = [
  { id: 'onchain', en: 'On-Chain Analytics', ko: '온체인 분석' },
  { id: 'defi', en: 'DeFi Research', ko: 'DeFi 연구' },
  { id: 'tokenomics', en: 'Tokenomics', ko: '토큰노믹스' },
  { id: 'macro', en: 'Macro & Crypto', ko: '거시 & 크립토' },
  { id: 'forensic', en: 'Forensic Risk', ko: '포렌식 리스크' },
  { id: 'nft', en: 'NFT & Gaming', ko: 'NFT & 게이밍' },
  { id: 'layer2', en: 'Layer 2 & Infra', ko: '레이어 2 & 인프라' },
  { id: 'regulation', en: 'Regulation & Compliance', ko: '규제 & 컴플라이언스' },
]

export default function OnboardingModal({ userId, referralCode, locale, onComplete }: OnboardingModalProps) {
  const isKo = locale === 'ko'
  const supabase = createClient()

  const [step, setStep] = useState(1)
  const [selectedInterests, setSelectedInterests] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  function toggleInterest(id: string) {
    setSelectedInterests((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  async function handleComplete() {
    setSaving(true)
    try {
      await supabase
        .from('profiles')
        .update({
          interests: selectedInterests,
          onboarding_completed: true,
          updated_at: new Date().toISOString(),
        })
        .eq('id', userId)

      onComplete()
    } catch (err) {
      console.error('Onboarding save error:', err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
      <div className="bg-gray-900 border border-white/10 rounded-2xl max-w-lg w-full p-8 shadow-2xl">

        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2 mb-6">
          {[1, 2].map((s) => (
            <div
              key={s}
              className={`w-8 h-1 rounded-full transition-colors ${s <= step ? 'bg-indigo-500' : 'bg-white/10'}`}
            />
          ))}
        </div>

        {/* Step 1: Interest selection */}
        {step === 1 && (
          <>
            <div className="text-center mb-6">
              <span className="text-3xl mb-3 block">👋</span>
              <h2 className="text-xl font-bold text-white">
                {isKo ? '환영합니다!' : 'Welcome!'}
              </h2>
              <p className="text-gray-400 text-sm mt-2">
                {isKo
                  ? '관심 있는 연구 분야를 선택하면 맞춤 콘텐츠를 추천해드립니다'
                  : 'Select your research interests for personalized recommendations'}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-6">
              {INTEREST_OPTIONS.map((opt) => {
                const selected = selectedInterests.includes(opt.id)
                return (
                  <button
                    key={opt.id}
                    onClick={() => toggleInterest(opt.id)}
                    className={`px-3 py-2.5 rounded-lg text-sm font-medium transition-all text-left ${
                      selected
                        ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                        : 'bg-white/5 text-gray-400 border border-white/5 hover:bg-white/10'
                    }`}
                  >
                    {selected ? '✓ ' : ''}{isKo ? opt.ko : opt.en}
                  </button>
                )
              })}
            </div>

            <button
              onClick={() => setStep(2)}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all"
            >
              {isKo ? '다음' : 'Next'}
            </button>

            <button
              onClick={handleComplete}
              className="w-full mt-2 py-2 text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              {isKo ? '나중에 하기' : 'Skip for now'}
            </button>
          </>
        )}

        {/* Step 2: Referral code + finish */}
        {step === 2 && (
          <>
            <div className="text-center mb-6">
              <span className="text-3xl mb-3 block">🎁</span>
              <h2 className="text-xl font-bold text-white">
                {isKo ? '내 추천 코드' : 'Your Referral Code'}
              </h2>
              <p className="text-gray-400 text-sm mt-2">
                {isKo
                  ? '친구에게 공유하면 보상을 받을 수 있습니다'
                  : 'Share with friends to earn rewards'}
              </p>
            </div>

            {/* Referral code display */}
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 text-center mb-6">
              <p className="text-xs text-gray-500 mb-1">
                {isKo ? '추천 코드' : 'Referral Code'}
              </p>
              <p className="text-2xl font-mono font-bold text-indigo-400 tracking-wider">
                {referralCode}
              </p>
              <button
                onClick={() => navigator.clipboard.writeText(referralCode)}
                className="mt-2 text-xs text-gray-500 hover:text-indigo-400 transition-colors"
              >
                {isKo ? '📋 복사하기' : '📋 Copy to clipboard'}
              </button>
            </div>

            {/* What you get summary */}
            <div className="space-y-2 mb-6 text-sm text-gray-400">
              <div className="flex items-center gap-2">
                <span className="text-green-400">✓</span>
                {isKo ? '전체 등급표 무제한 열람' : 'Full maturity rankings access'}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-green-400">✓</span>
                {isKo ? 'Executive Summary 다운로드' : 'Executive Summary downloads'}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-green-400">✓</span>
                {isKo ? '첫 구매 20% 할인 쿠폰 발급 완료' : '20% off first purchase coupon active'}
              </div>
            </div>

            <button
              onClick={handleComplete}
              disabled={saving}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white font-semibold rounded-xl transition-all"
            >
              {saving
                ? (isKo ? '저장 중…' : 'Saving…')
                : (isKo ? '시작하기' : 'Get Started')}
            </button>

            <button
              onClick={() => setStep(1)}
              className="w-full mt-2 py-2 text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              ← {isKo ? '이전' : 'Back'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
