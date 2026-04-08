'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { type Product } from '@/lib/types'

const CRYPTOS = [
  { symbol: 'BTC', name: 'Bitcoin', icon: '₿', color: 'text-orange-400' },
  { symbol: 'ETH', name: 'Ethereum', icon: 'Ξ', color: 'text-blue-400' },
  { symbol: 'USDT', name: 'Tether', icon: '₮', color: 'text-green-400' },
  { symbol: 'USDC', name: 'USD Coin', icon: '$', color: 'text-blue-300' },
]

interface Props {
  product: Product
}

export default function CryptoPayment({ product }: Props) {
  const t = useTranslations('checkout')
  const [selectedCrypto, setSelectedCrypto] = useState<string | null>(null)
  const [paymentInfo, setPaymentInfo] = useState<{
    amount: string
    address: string
    price: number
  } | null>(null)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<'select' | 'awaiting' | 'confirming' | 'confirmed' | 'failed'>('select')

  async function initCryptoPayment(currency: string) {
    setSelectedCrypto(currency)
    setLoading(true)
    try {
      const res = await fetch('/api/crypto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ productId: product.id, currency }),
      })
      const data = await res.json()
      setPaymentInfo(data)
      setStatus('awaiting')
    } catch (err) {
      console.error(err)
      setStatus('failed')
    } finally {
      setLoading(false)
    }
  }

  // Poll for confirmation
  useEffect(() => {
    if (status !== 'awaiting' || !paymentInfo) return
    const interval = setInterval(async () => {
      // In production, poll your backend for tx confirmation
      // For demo, we show the awaiting state
    }, 15000)
    return () => clearInterval(interval)
  }, [status, paymentInfo])

  if (status === 'awaiting' && paymentInfo) {
    const crypto = CRYPTOS.find(c => c.symbol === selectedCrypto)!
    return (
      <div className="space-y-4">
        <div className="p-4 rounded-xl bg-white/5 border border-white/10 text-center">
          <p className="text-sm text-gray-400 mb-2">
            {t('sendExactAmount', { amount: paymentInfo.amount, currency: selectedCrypto ?? '' })}
          </p>
          <div className="p-3 bg-gray-900 rounded-lg font-mono text-sm text-indigo-400 break-all select-all">
            {paymentInfo.address}
          </div>
          <div className="mt-4 flex items-center justify-center gap-2 text-sm text-yellow-400">
            <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            {t('waitingConfirmation')}
          </div>
        </div>
        <p className="text-xs text-gray-600 text-center">
          1 {selectedCrypto} ≈ ${paymentInfo.price.toLocaleString()} USD
        </p>
      </div>
    )
  }

  if (status === 'confirmed') {
    return (
      <div className="p-6 rounded-xl bg-green-500/10 border border-green-500/20 text-center">
        <span className="text-4xl">✓</span>
        <p className="text-green-400 font-semibold mt-2">{t('paymentSuccess')}</p>
      </div>
    )
  }

  return (
    <div>
      <p className="text-sm text-gray-400 mb-3">{t('selectCrypto')}</p>
      <div className="grid grid-cols-2 gap-2">
        {CRYPTOS.map((crypto) => (
          <button
            key={crypto.symbol}
            onClick={() => initCryptoPayment(crypto.symbol)}
            disabled={loading}
            className="p-3 rounded-xl bg-white/5 border border-white/10 hover:border-indigo-500/30 hover:bg-indigo-500/5 transition-all text-center disabled:opacity-50"
          >
            <span className={`text-2xl ${crypto.color}`}>{crypto.icon}</span>
            <p className="text-xs text-gray-400 mt-1">{crypto.name}</p>
            <p className="text-xs text-gray-600">{crypto.symbol}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
