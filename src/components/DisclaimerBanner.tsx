'use client'

import Link from 'next/link'
import { useLocale } from 'next-intl'

interface DisclaimerBannerProps {
  compact?: boolean
}

const disclaimerText: Record<string, string> = {
  en: 'This content is produced by Blockchain Economics Lab for informational and educational purposes only. It does not constitute financial, investment, or trading advice. Cryptocurrency markets carry significant risk. Users are solely responsible for their own trading decisions.',
  ko: '이 콘텐츠는 블록체인 경제 연구소가 정보 제공 및 교육 목적으로만 제작한 것입니다. 금융, 투자 또는 거래 조언을 구성하지 않습니다. 암호화폐 시장에는 상당한 위험이 따릅니다. 사용자는 자신의 거래 결정에 대해 전적으로 책임을 집니다.',
}

export default function DisclaimerBanner({ compact = false }: DisclaimerBannerProps) {
  const locale = useLocale()
  const text = disclaimerText[locale] || disclaimerText.en

  if (compact) {
    return (
      <p className="text-xs text-gray-600 mt-4">
        Not financial advice.{' '}
        <Link href={`/${locale}/disclaimer`} className="underline hover:text-gray-400 transition-colors">
          Full disclaimer
        </Link>
      </p>
    )
  }

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4">
      <p className="text-xs text-gray-500 leading-relaxed">
        <strong className="text-gray-400">Disclaimer:</strong>{' '}
        {text}{' '}
        <Link href={`/${locale}/disclaimer`} className="text-indigo-500 hover:text-indigo-400 transition-colors">
          Read full disclaimer →
        </Link>
      </p>
    </div>
  )
}
