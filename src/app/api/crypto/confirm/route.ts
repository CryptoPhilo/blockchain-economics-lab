import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { cryptoConfirmLimiter, getRateLimitId, rateLimitResponse } from '@/lib/rate-limit'

/**
 * POST /api/crypto/confirm
 * Polls blockchain for crypto payment confirmation.
 * Called by client after user sends crypto payment.
 *
 * Body: { order_id: string }
 * Returns: { status: 'pending' | 'confirmed' | 'failed', confirmations?: number }
 */

// STRIX-SS-002: Validate transaction hash format
const ETH_TX_HASH_RE = /^0x[a-fA-F0-9]{64}$/
const BTC_TX_HASH_RE = /^[a-fA-F0-9]{64}$/

const MIN_CONFIRMATIONS: Record<string, number> = {
  crypto_btc: 3,
  crypto_eth: 12,
  crypto_usdt: 12,
  crypto_usdc: 12,
}

// Etherscan / blockchain explorer APIs (placeholder — replace with production keys)
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || ''
const ETHERSCAN_API = 'https://api.etherscan.io/api'

interface EtherscanTxResult {
  status: string
  result: {
    isError: string
    blockNumber: string
    confirmations: string
    value: string
    to: string
  }
}

async function checkEthTxConfirmation(txHash: string): Promise<{
  confirmed: boolean
  confirmations: number
  toAddress: string
  valueWei: string
}> {
  // FIX 3: Require ETHERSCAN_API_KEY instead of simulating
  if (!ETHERSCAN_API_KEY) {
    console.error('[Crypto] ETHERSCAN_API_KEY not configured')
    throw new Error('Payment verification unavailable')
  }

  try {
    const url = `${ETHERSCAN_API}?module=transaction&action=gettxreceiptstatus&txhash=${txHash}&apikey=${ETHERSCAN_API_KEY}`
    const response = await fetch(url)
    const data: EtherscanTxResult = await response.json()

    if (data.status === '1' && data.result) {
      const confirmations = parseInt(data.result.confirmations || '0', 10)
      return {
        confirmed: confirmations >= MIN_CONFIRMATIONS.crypto_eth,
        confirmations,
        toAddress: data.result.to || '',
        valueWei: data.result.value || '0',
      }
    }

    return { confirmed: false, confirmations: 0, toAddress: '', valueWei: '0' }
  } catch (error) {
    console.error('[Crypto] Etherscan check failed:', error)
    return { confirmed: false, confirmations: 0, toAddress: '', valueWei: '0' }
  }
}

export async function POST(request: NextRequest) {
  try {
    const { order_id } = await request.json()

    if (!order_id) {
      return NextResponse.json({ error: 'order_id is required' }, { status: 400 })
    }

    const supabase = await createServerSupabaseClient()

    // FIX 1: Require authentication
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 })
    }

    // STRIX-INFRA-002: Rate limit crypto confirm polling (30/min per user)
    const rlResult = cryptoConfirmLimiter.check(getRateLimitId(request, user.id))
    if (!rlResult.success) {
      return rateLimitResponse(rlResult)
    }

    // Fetch order
    const { data: order, error: orderError } = await supabase
      .from('orders')
      .select('id, user_id, status, payment_method, crypto_amount, crypto_currency, crypto_tx_hash, total_cents')
      .eq('id', order_id)
      .single()

    if (orderError || !order) {
      return NextResponse.json({ error: 'Order not found' }, { status: 404 })
    }

    // FIX 2: Verify order ownership
    if (order.user_id !== user.id) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
    }

    // Already completed or failed
    if (order.status === 'completed') {
      return NextResponse.json({ status: 'confirmed', confirmations: 999 })
    }
    if (order.status === 'failed' || order.status === 'refunded') {
      return NextResponse.json({ status: 'failed' })
    }

    // No TX hash yet — user hasn't submitted payment
    if (!order.crypto_tx_hash) {
      return NextResponse.json({ status: 'pending', confirmations: 0 })
    }

    const paymentMethod = order.payment_method as string

    // STRIX-SS-002: Validate tx_hash format before using in external API calls
    const txHash = order.crypto_tx_hash as string
    if (paymentMethod.startsWith('crypto_eth') || paymentMethod === 'crypto_usdt' || paymentMethod === 'crypto_usdc') {
      if (!ETH_TX_HASH_RE.test(txHash)) {
        return NextResponse.json({ error: 'Invalid transaction hash format' }, { status: 400 })
      }
    } else if (paymentMethod === 'crypto_btc') {
      if (!BTC_TX_HASH_RE.test(txHash)) {
        return NextResponse.json({ error: 'Invalid transaction hash format' }, { status: 400 })
      }
    }

    // Check based on payment method
    if (paymentMethod === 'crypto_eth' || paymentMethod === 'crypto_usdt' || paymentMethod === 'crypto_usdc') {
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const result = await checkEthTxConfirmation(order.crypto_tx_hash as any)

        if (result.confirmed) {
          // Mark order as completed
          await supabase
            .from('orders')
            .update({
              status: 'completed',
              paid_at: new Date().toISOString(),
            })
            .eq('id', order_id)
            .eq('status', 'pending')

          // Grant access to purchased products
          const { data: items } = await supabase
            .from('order_items')
            .select('product_id')
            .eq('order_id', order_id)

          if (items && items.length > 0) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const libraryInserts = items.map((item: any) => ({
              user_id: order.user_id || '',
              product_id: item.product_id,
              order_id: order_id,
              access_granted_at: new Date().toISOString(),
              download_count: 0,
            }))

            await supabase.from('user_library').insert(libraryInserts)
          }

          return NextResponse.json({
            status: 'confirmed',
            confirmations: result.confirmations,
          })
        }

        return NextResponse.json({
          status: 'pending',
          confirmations: result.confirmations,
        })
      } catch (err) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        console.error('[Crypto] ETH check failed:', err as any)
        return NextResponse.json({ error: 'Payment verification unavailable' }, { status: 503 })
      }
    }

    if (paymentMethod === 'crypto_btc') {
      // BTC confirmation check via mempool.space API (no key needed)
      try {
        const mempoolUrl = `https://mempool.space/api/tx/${order.crypto_tx_hash}`
        const response = await fetch(mempoolUrl)

        if (response.ok) {
          const txData = await response.json()
          const isConfirmed = txData.status?.confirmed === true
          const blockHeight = txData.status?.block_height || 0

          if (isConfirmed) {
            // Get current block height for confirmation count
            const tipRes = await fetch('https://mempool.space/api/blocks/tip/height')
            const tipHeight = tipRes.ok ? parseInt(await tipRes.text(), 10) : 0
            const confirmations = tipHeight > 0 ? tipHeight - blockHeight + 1 : 1

            if (confirmations >= MIN_CONFIRMATIONS.crypto_btc) {
              // FIX 4: Add optimistic locking to prevent race conditions
              await supabase
                .from('orders')
                .update({
                  status: 'completed',
                  paid_at: new Date().toISOString(),
                })
                .eq('id', order_id)
                .eq('status', 'pending')

              // Grant library access
              const { data: items } = await supabase
                .from('order_items')
                .select('product_id')
                .eq('order_id', order_id)

              if (items && items.length > 0) {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const libraryInserts = items.map((item: any) => ({
                  user_id: order.user_id || '',
                  product_id: item.product_id,
                  order_id: order_id,
                  access_granted_at: new Date().toISOString(),
                  download_count: 0,
                }))
                await supabase.from('user_library').insert(libraryInserts)
              }

              return NextResponse.json({ status: 'confirmed', confirmations })
            }

            return NextResponse.json({ status: 'pending', confirmations })
          }
        }
      } catch (err) {
        console.error('[Crypto] BTC check failed:', err)
      }

      return NextResponse.json({ status: 'pending', confirmations: 0 })
    }

    return NextResponse.json({ error: 'Unsupported payment method' }, { status: 400 })
  } catch (error) {
    console.error('[Crypto] Confirm error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
