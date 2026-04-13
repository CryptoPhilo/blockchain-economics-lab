'use client'

import { useLocale } from 'next-intl'

interface ReferralCTAProps {
  exchange: string
  token: string
  isRestricted: boolean
  source?: string
  contentId?: string
  variant?: 'default' | 'compact' | 'banner'
}

const exchangeConfig: Record<string, { name: string; color: string }> = {
  binance: { name: 'Binance', color: 'text-yellow-400 hover:text-yellow-300' },
  bybit: { name: 'Bybit', color: 'text-orange-400 hover:text-orange-300' },
  okx: { name: 'OKX', color: 'text-blue-400 hover:text-blue-300' },
}

export default function ReferralCTA({
  exchange,
  token,
  isRestricted,
  source = 'web',
  contentId,
  variant = 'default',
}: ReferralCTAProps) {
  const locale = useLocale()
  const config = exchangeConfig[exchange] || { name: exchange, color: 'text-indigo-400 hover:text-indigo-300' }

  if (isRestricted) {
    return (
      <span className="text-gray-500 text-sm">
        {locale === 'ko' ? `${config.name}에서 ${token} 자세히 보기` : `Learn more about ${token} on ${config.name}`} →
      </span>
    )
  }

  const referralUrl = `/api/referral/redirect?exchange=${exchange}&source=${source}${contentId ? `&content_id=${contentId}` : ''}`

  if (variant === 'compact') {
    return (
      <a
        href={referralUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={`text-sm font-medium ${config.color} transition-colors`}
      >
        Trade {token} on {config.name} →
      </a>
    )
  }

  if (variant === 'banner') {
    return (
      <div className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/10 hover:border-indigo-500/30 transition-colors">
        <div className="flex-1">
          <p className="text-sm font-medium text-white">
            Ready to act on this research?
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            Open your position on a trusted exchange
          </p>
        </div>
        <a
          href={referralUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap"
        >
          Trade {token} on {config.name} →
        </a>
      </div>
    )
  }

  return (
    <a
      href={referralUrl}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1.5 font-medium ${config.color} transition-colors`}
    >
      Trade {token} on {config.name} →
    </a>
  )
}
