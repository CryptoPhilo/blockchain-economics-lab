'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { type Product } from '@/lib/types'
import CryptoPayment from './CryptoPayment'

interface Props {
  product: Product
  locale: string
}

export default function CheckoutButton({ product, locale }: Props) {
  const t = useTranslations('checkout')
  const [paymentMode, setPaymentMode] = useState<'select' | 'stripe' | 'crypto'>('select')
  const [loading, setLoading] = useState(false)

  async function handleStripeCheckout() {
    setLoading(true)
    try {
      const res = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ productId: product.id, locale }),
      })
      const { url } = await res.json()
      if (url) window.location.href = url
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  if (paymentMode === 'crypto') {
    return (
      <div>
        <button onClick={() => setPaymentMode('select')} className="text-sm text-gray-500 hover:text-gray-300 mb-4">
          ← {t('paymentMethod')}
        </button>
        <CryptoPayment product={product} />
      </div>
    )
  }

  if (paymentMode === 'stripe') {
    return (
      <div>
        <button onClick={() => setPaymentMode('select')} className="text-sm text-gray-500 hover:text-gray-300 mb-4">
          ← {t('paymentMethod')}
        </button>
        <button
          onClick={handleStripeCheckout}
          disabled={loading}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 text-white font-semibold rounded-xl transition-all"
        >
          {loading ? t('processing') : t('payWithStripe')}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <button
        onClick={() => setPaymentMode('stripe')}
        className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
      >
        💳 {t('creditCard')}
      </button>
      <button
        onClick={() => setPaymentMode('crypto')}
        className="w-full py-3 bg-white/5 hover:bg-white/10 text-white font-semibold rounded-xl border border-white/10 transition-all flex items-center justify-center gap-2"
      >
        🔗 {t('crypto')}
      </button>
    </div>
  )
}
