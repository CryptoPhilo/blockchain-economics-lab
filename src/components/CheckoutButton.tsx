'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { type Product } from '@/lib/types'
import CryptoPayment from './CryptoPayment'

interface Props {
  product: Product
  locale: string
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function CheckoutButton({ product, locale }: Props) {
  const t = useTranslations('checkout')
  const [showCrypto, setShowCrypto] = useState(false)

  if (showCrypto) {
    return (
      <div>
        <button onClick={() => setShowCrypto(false)} className="text-sm text-gray-500 hover:text-gray-300 mb-4">
          ← {t('paymentMethod')}
        </button>
        <CryptoPayment product={product} />
      </div>
    )
  }

  return (
    <div>
      <button
        onClick={() => setShowCrypto(true)}
        className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
      >
        🔗 {t('payWithCrypto')}
      </button>
      <div className="flex justify-center gap-4 mt-3 text-sm text-gray-500">
        <span>₿ BTC</span>
        <span>Ξ ETH</span>
        <span>₮ USDT</span>
        <span>$ USDC</span>
      </div>
    </div>
  )
}
