'use client'

import Link from 'next/link'
import { useLocale } from 'next-intl'

interface FreemiumPaywallProps {
  reportType: 'econ' | 'maturity' | 'forensic'
}

const paywallConfig = {
  econ: {
    icon: '📊',
    freeLabel: '40% Free Preview',
    message_en: 'Additional economic analysis is being prepared, including scenario modeling, regulatory compliance scoring, and actionable investment framework updates.',
    message_ko: '시나리오 모델링, 규제 준수 점수, 실행 가능한 투자 프레임워크 업데이트를 포함한 추가 경제 분석을 준비 중입니다.',
    gradient: 'from-blue-500/10 to-indigo-500/10',
    border: 'border-blue-500/20',
  },
  maturity: {
    icon: '📈',
    freeLabel: '35% Free Preview',
    message_en: 'Additional maturity assessment material is being prepared, including scoring breakdowns, sector benchmark comparisons, and narrative health updates.',
    message_ko: '상세 점수 분석, 섹터 벤치마크 비교, 내러티브 건강 업데이트를 포함한 추가 성숙도 평가 자료를 준비 중입니다.',
    gradient: 'from-green-500/10 to-emerald-500/10',
    border: 'border-green-500/20',
  },
  forensic: {
    icon: '🔍',
    freeLabel: '50% Free Preview',
    message_en: 'Additional risk material is being prepared, including fund flow analysis, economic attack vector analysis, probability-weighted scenarios, and response actions.',
    message_ko: '자금 흐름 분석, 경제적 공격 벡터 분석, 확률 가중 시나리오, 대응 조치를 포함한 추가 리스크 자료를 준비 중입니다.',
    gradient: 'from-red-500/10 to-orange-500/10',
    border: 'border-red-500/20',
  },
}

export default function FreemiumPaywall({ reportType }: FreemiumPaywallProps) {
  const locale = useLocale()
  const config = paywallConfig[reportType]
  const message = locale === 'ko' ? config.message_ko : config.message_en

  return (
    <div className={`relative rounded-2xl bg-gradient-to-br ${config.gradient} border ${config.border} p-8 text-center my-8`}>
      {/* Lock icon */}
      <div className="w-16 h-16 rounded-full bg-white/10 flex items-center justify-center mx-auto mb-4">
        <span className="text-3xl">🔒</span>
      </div>

      {/* Free preview badge */}
      <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 text-sm text-gray-300 mb-4">
        <span>{config.icon}</span>
        <span>{config.freeLabel}</span>
      </div>

      <h3 className="text-xl font-bold text-white mb-3">
        {locale === 'ko' ? '무료 업데이트를 받아보세요' : 'Get Free Updates'}
      </h3>

      <p className="text-gray-400 text-sm max-w-lg mx-auto mb-6 leading-relaxed">
        {message}
      </p>

      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Link
          href={`/${locale}#newsletter`}
          className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg"
        >
          {locale === 'ko' ? '무료 뉴스레터 구독' : 'Subscribe to the Free Newsletter'}
        </Link>
      </div>

      {/* 360° badge */}
      <p className="text-xs text-gray-600 mt-6">
        🔄 360° Project Intelligence — Economics + Maturity + Risk updates by email
      </p>
    </div>
  )
}
