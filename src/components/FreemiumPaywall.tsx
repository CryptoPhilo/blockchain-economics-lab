'use client'

import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'

interface FreemiumPaywallProps {
  reportType: 'econ' | 'maturity' | 'forensic'
  productSlug?: string
  priceUsd?: number
}

const paywallConfig = {
  econ: {
    icon: '📊',
    freeLabel: '40% Free Preview',
    message_en: 'Full economic analysis continues with 7 more chapters, including Monte Carlo scenario modeling, regulatory compliance scoring, and actionable investment framework.',
    message_ko: '몬테카를로 시나리오 모델링, 규제 준수 점수, 실행 가능한 투자 프레임워크를 포함한 7개 추가 챕터의 전체 경제 분석이 계속됩니다.',
    gradient: 'from-blue-500/10 to-indigo-500/10',
    border: 'border-blue-500/20',
    button: 'bg-blue-600 hover:bg-blue-500',
  },
  maturity: {
    icon: '📈',
    freeLabel: '35% Free Preview',
    message_en: 'Complete 7-axis maturity assessment with detailed scoring breakdown, sector benchmark comparison, and narrative health analysis continues behind the paywall.',
    message_ko: '상세 점수 분석, 섹터 벤치마크 비교, 내러티브 건강 분석을 포함한 7축 성숙도 평가 전문이 유료 벽 뒤에서 계속됩니다.',
    gradient: 'from-green-500/10 to-emerald-500/10',
    border: 'border-green-500/20',
    button: 'bg-green-600 hover:bg-green-500',
  },
  forensic: {
    icon: '🔍',
    freeLabel: '50% Free Preview',
    message_en: 'Full risk assessment with fund flow analysis, economic attack vector analysis, probability-weighted scenarios, and risk response actions continues in the full report.',
    message_ko: '자금 흐름 분석, 경제적 공격 벡터 분석, 확률 가중 시나리오, 리스크 대응 조치를 포함한 전체 리스크 평가가 정식 보고서에서 계속됩니다.',
    gradient: 'from-red-500/10 to-orange-500/10',
    border: 'border-red-500/20',
    button: 'bg-red-600 hover:bg-red-500',
  },
}

export default function FreemiumPaywall({ reportType, productSlug, priceUsd }: FreemiumPaywallProps) {
  const locale = useLocale()
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const t = useTranslations()
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
        {locale === 'ko' ? '전체 분석을 확인하세요' : 'Unlock the Full Analysis'}
      </h3>

      <p className="text-gray-400 text-sm max-w-lg mx-auto mb-6 leading-relaxed">
        {message}
      </p>

      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        {productSlug && (
          <Link
            href={`/${locale}/products/${productSlug}`}
            className={`px-6 py-3 ${config.button} text-white font-semibold rounded-xl transition-all shadow-lg`}
          >
            {locale === 'ko' ? '전체 보고서 구매' : 'Buy Full Report'}
            {priceUsd && ` ($${priceUsd})`}
          </Link>
        )}
        <Link
          href={`/${locale}/products?type=subscription`}
          className="px-6 py-3 bg-white/5 hover:bg-white/10 text-white font-semibold rounded-xl border border-white/10 transition-all"
        >
          {locale === 'ko' ? '구독으로 절약하기' : 'Subscribe & Save'} ($19/mo)
        </Link>
      </div>

      {/* 360° badge */}
      <p className="text-xs text-gray-600 mt-6">
        🔄 360° Project Intelligence — Economics + Maturity + Risk in one subscription
      </p>
    </div>
  )
}
