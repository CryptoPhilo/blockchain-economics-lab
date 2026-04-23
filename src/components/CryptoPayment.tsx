'use client'

import { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { type Product } from '@/lib/types'

const CRYPTOS = [
  { symbol: 'BTC', name: 'Bitcoin', icon: '₿', color: 'text-orange-400' },
  { symbol: 'ETH', name: 'Ethereum', icon: 'Ξ', color: 'text-blue-400' },
  { symbol: 'USDT', name: 'Tether', icon: '₮', color: 'text-green-400' },
  { symbol: 'USDC', name: 'USD Coin', icon: '$', color: 'text-blue-300' },
]

interface PaymentInfo {
  orderId: string
  amount: string
  address: string
  currency: string
  network: string
  price: number
  expiresAt: string
}

interface Props {
  product: Product
}

export default function CryptoPayment({ product }: Props) {
  const t = useTranslations('checkout')
  const [selectedCrypto, setSelectedCrypto] = useState<string | null>(null)
  const [paymentInfo, setPaymentInfo] = useState<PaymentInfo | null>(null)
  const [txHash, setTxHash] = useState('')
  const [loading, setLoading] = useState(false)
  const [submittingHash, setSubmittingHash] = useState(false)
  const [status, setStatus] = useState<'select' | 'awaiting' | 'confirming' | 'confirmed' | 'failed'>('select')
  const [message, setMessage] = useState<string | null>(null)

  async function initCryptoPayment(currency: string) {
    setSelectedCrypto(currency)
    setLoading(true)
    setMessage(null)

    try {
      const res = await fetch('/api/crypto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ productId: product.id, currency }),
      })
      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || 'Failed to initialize crypto payment')
      }

      setPaymentInfo(data)
      setStatus('awaiting')
      setTxHash('')
    } catch (error) {
      console.error(error)
      setStatus('failed')
      setMessage(error instanceof Error ? error.message : 'Failed to initialize payment')
    } finally {
      setLoading(false)
    }
  }

  async function submitTransactionHash() {
    if (!paymentInfo || !txHash.trim()) {
      return
    }

    setSubmittingHash(true)
    setMessage(null)

    try {
      const res = await fetch('/api/crypto/confirm', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          order_id: paymentInfo.orderId,
          tx_hash: txHash.trim(),
        }),
      })
      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || 'Failed to submit transaction hash')
      }

      setStatus('confirming')
    } catch (error) {
      console.error(error)
      setMessage(error instanceof Error ? error.message : 'Failed to submit transaction hash')
    } finally {
      setSubmittingHash(false)
    }
  }

  useEffect(() => {
    if ((status !== 'awaiting' && status !== 'confirming') || !paymentInfo || !txHash.trim()) {
      return
    }

    let cancelled = false
    const poll = async () => {
      try {
        const res = await fetch('/api/crypto/confirm', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ order_id: paymentInfo.orderId }),
        })
        const data = await res.json()

        if (!res.ok || cancelled) {
          if (!cancelled) {
            setMessage(data.error || 'Failed to verify payment')
            setStatus('failed')
          }
          return
        }

        if (data.status === 'confirmed') {
          setStatus('confirmed')
          return
        }

        if (data.status === 'failed') {
          setStatus('failed')
          setMessage('Payment verification failed')
          return
        }

        setStatus(data.txHashSubmitted ? 'confirming' : 'awaiting')
      } catch (error) {
        if (!cancelled) {
          console.error(error)
        }
      }
    }

    void poll()
    const interval = window.setInterval(() => void poll(), 15000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [paymentInfo, status, txHash])

  if ((status === 'awaiting' || status === 'confirming') && paymentInfo) {
    const crypto = CRYPTOS.find((item) => item.symbol === selectedCrypto)
    const isSubmitted = status === 'confirming'

    return (
      <div className="space-y-4">
        <div className="p-4 rounded-xl bg-white/5 border border-white/10 text-center">
          <p className="text-sm text-gray-400 mb-2">
            {t('sendExactAmount', { amount: paymentInfo.amount, currency: selectedCrypto ?? '' })}
          </p>
          <div className="p-3 bg-gray-900 rounded-lg font-mono text-sm text-indigo-400 break-all select-all">
            {paymentInfo.address}
          </div>
          <p className="mt-3 text-xs text-gray-500">
            {paymentInfo.network} · 1 {selectedCrypto} ≈ ${paymentInfo.price.toLocaleString()} USD
          </p>
          <div className="mt-4 flex items-center justify-center gap-2 text-sm text-yellow-400">
            <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            {isSubmitted ? t('waitingConfirmation') : `${crypto?.name || selectedCrypto} tx hash required`}
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="crypto-tx-hash" className="block text-sm text-gray-300">
            Transaction hash
          </label>
          <input
            id="crypto-tx-hash"
            value={txHash}
            onChange={(event) => setTxHash(event.target.value)}
            placeholder={selectedCrypto === 'BTC' ? '64-char tx hash' : '0x...'}
            className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition-colors focus:border-indigo-400"
          />
          <button
            onClick={submitTransactionHash}
            disabled={submittingHash || !txHash.trim()}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-xl transition-all"
          >
            {submittingHash ? 'Submitting...' : isSubmitted ? 'Re-submit tx hash' : 'Submit tx hash'}
          </button>
        </div>

        {message && (
          <p className="text-sm text-rose-300">{message}</p>
        )}
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

  if (status === 'failed') {
    return (
      <div className="space-y-4">
        <div className="rounded-xl border border-rose-400/20 bg-rose-500/10 p-4 text-sm text-rose-200">
          {message || 'Unable to complete the crypto payment flow.'}
        </div>
        <button
          onClick={() => {
            setStatus('select')
            setSelectedCrypto(null)
            setPaymentInfo(null)
            setTxHash('')
            setMessage(null)
          }}
          className="w-full py-3 bg-white/10 hover:bg-white/15 text-white font-semibold rounded-xl transition-all"
        >
          Try again
        </button>
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
