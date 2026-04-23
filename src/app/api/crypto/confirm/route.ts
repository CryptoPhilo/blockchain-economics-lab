import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import { fulfillOrderEntitlements } from '@/lib/purchase-fulfillment'
import { cryptoConfirmLimiter, getRateLimitId, rateLimitResponse } from '@/lib/rate-limit'

const ETH_TX_HASH_RE = /^0x[a-fA-F0-9]{64}$/
const BTC_TX_HASH_RE = /^[a-fA-F0-9]{64}$/

const MIN_CONFIRMATIONS: Record<string, number> = {
  crypto_btc: 3,
  crypto_eth: 12,
  crypto_usdt: 12,
  crypto_usdc: 12,
}

const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || ''
const ETHERSCAN_API = 'https://api.etherscan.io/api'

interface OrderRecord {
  id: string
  user_id: string
  status: string
  payment_method: string
  crypto_tx_hash?: string | null
}

function validateTxHash(paymentMethod: string, txHash: string) {
  if (
    (paymentMethod === 'crypto_eth' || paymentMethod === 'crypto_usdt' || paymentMethod === 'crypto_usdc') &&
    !ETH_TX_HASH_RE.test(txHash)
  ) {
    return false
  }

  if (paymentMethod === 'crypto_btc' && !BTC_TX_HASH_RE.test(txHash)) {
    return false
  }

  return true
}

async function loadAuthorizedOrder(request: NextRequest, orderId: string) {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    return { error: NextResponse.json({ error: 'Authentication required' }, { status: 401 }) }
  }

  const rlResult = cryptoConfirmLimiter.check(getRateLimitId(request, user.id))
  if (!rlResult.success) {
    return { error: rateLimitResponse(rlResult) }
  }

  const { data: order, error } = await supabase
    .from('orders')
    .select('id, user_id, status, payment_method, crypto_tx_hash')
    .eq('id', orderId)
    .single()

  if (error || !order) {
    return { error: NextResponse.json({ error: 'Order not found' }, { status: 404 }) }
  }

  if (order.user_id !== user.id) {
    return { error: NextResponse.json({ error: 'Forbidden' }, { status: 403 }) }
  }

  return { supabase, user, order: order as OrderRecord }
}

async function checkEthTxConfirmation(txHash: string) {
  if (!ETHERSCAN_API_KEY) {
    throw new Error('Payment verification unavailable')
  }

  const [txResponse, blockResponse] = await Promise.all([
    fetch(
      `${ETHERSCAN_API}?module=proxy&action=eth_getTransactionByHash&txhash=${txHash}&apikey=${ETHERSCAN_API_KEY}`,
      { cache: 'no-store' }
    ),
    fetch(
      `${ETHERSCAN_API}?module=proxy&action=eth_blockNumber&apikey=${ETHERSCAN_API_KEY}`,
      { cache: 'no-store' }
    ),
  ])

  if (!txResponse.ok || !blockResponse.ok) {
    return { confirmed: false, confirmations: 0 }
  }

  const txData = await txResponse.json()
  const blockData = await blockResponse.json()
  const txBlock = typeof txData.result?.blockNumber === 'string' ? parseInt(txData.result.blockNumber, 16) : 0
  const latestBlock = typeof blockData.result === 'string' ? parseInt(blockData.result, 16) : 0

  if (!txBlock || !latestBlock) {
    return { confirmed: false, confirmations: 0 }
  }

  const confirmations = Math.max(latestBlock - txBlock + 1, 0)
  return {
    confirmed: confirmations >= MIN_CONFIRMATIONS.crypto_eth,
    confirmations,
  }
}

async function checkBtcTxConfirmation(txHash: string) {
  const response = await fetch(`https://mempool.space/api/tx/${txHash}`, { cache: 'no-store' })
  if (!response.ok) {
    return { confirmed: false, confirmations: 0 }
  }

  const txData = await response.json()
  if (txData.status?.confirmed !== true) {
    return { confirmed: false, confirmations: 0 }
  }

  const blockHeight = txData.status?.block_height || 0
  const tipRes = await fetch('https://mempool.space/api/blocks/tip/height', { cache: 'no-store' })
  const tipHeight = tipRes.ok ? parseInt(await tipRes.text(), 10) : 0
  const confirmations = tipHeight > 0 ? tipHeight - blockHeight + 1 : 1

  return {
    confirmed: confirmations >= MIN_CONFIRMATIONS.crypto_btc,
    confirmations,
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const { order_id, tx_hash } = await request.json()

    if (!order_id || !tx_hash) {
      return NextResponse.json({ error: 'order_id and tx_hash are required' }, { status: 400 })
    }

    const loaded = await loadAuthorizedOrder(request, order_id)
    if (loaded.error) {
      return loaded.error
    }

    const normalizedHash = String(tx_hash).trim()
    if (!validateTxHash(loaded.order.payment_method, normalizedHash)) {
      return NextResponse.json({ error: 'Invalid transaction hash format' }, { status: 400 })
    }

    if (loaded.order.status !== 'pending') {
      return NextResponse.json({ error: 'Order is no longer pending' }, { status: 409 })
    }

    const adminSupabase = createSupabaseAdminClient()
    const { error } = await adminSupabase
      .from('orders')
      .update({ crypto_tx_hash: normalizedHash })
      .eq('id', order_id)

    if (error) {
      console.error('[Crypto] Failed to save transaction hash:', error)
      return NextResponse.json({ error: 'Failed to save transaction hash' }, { status: 500 })
    }

    return NextResponse.json({ ok: true })
  } catch (error) {
    console.error('[Crypto] Submit hash error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const { order_id } = await request.json()
    if (!order_id) {
      return NextResponse.json({ error: 'order_id is required' }, { status: 400 })
    }

    const loaded = await loadAuthorizedOrder(request, order_id)
    if (loaded.error) {
      return loaded.error
    }

    const { user, order } = loaded

    if (order.status === 'completed') {
      return NextResponse.json({ status: 'confirmed', confirmations: 999 })
    }

    if (order.status === 'failed' || order.status === 'refunded') {
      return NextResponse.json({ status: 'failed' })
    }

    if (!order.crypto_tx_hash) {
      return NextResponse.json({ status: 'pending', confirmations: 0, txHashSubmitted: false })
    }

    if (!validateTxHash(order.payment_method, order.crypto_tx_hash)) {
      return NextResponse.json({ error: 'Invalid transaction hash format' }, { status: 400 })
    }

    let result = { confirmed: false, confirmations: 0 }

    if (
      order.payment_method === 'crypto_eth' ||
      order.payment_method === 'crypto_usdt' ||
      order.payment_method === 'crypto_usdc'
    ) {
      try {
        result = await checkEthTxConfirmation(order.crypto_tx_hash)
      } catch (error) {
        console.error('[Crypto] ETH check failed:', error)
        return NextResponse.json({ error: 'Payment verification unavailable' }, { status: 503 })
      }
    } else if (order.payment_method === 'crypto_btc') {
      try {
        result = await checkBtcTxConfirmation(order.crypto_tx_hash)
      } catch (error) {
        console.error('[Crypto] BTC check failed:', error)
      }
    } else {
      return NextResponse.json({ error: 'Unsupported payment method' }, { status: 400 })
    }

    if (!result.confirmed) {
      return NextResponse.json({
        status: 'pending',
        confirmations: result.confirmations,
        txHashSubmitted: true,
      })
    }

    try {
      await fulfillOrderEntitlements({
        supabase: createSupabaseAdminClient(),
        orderId: order_id,
        userId: user.id,
        paymentMethod: order.payment_method as 'crypto_btc' | 'crypto_eth' | 'crypto_usdt' | 'crypto_usdc',
      })
    } catch (error) {
      console.error('[Crypto] Fulfillment failed:', error)
      return NextResponse.json({ error: 'Failed to grant access' }, { status: 500 })
    }

    return NextResponse.json({
      status: 'confirmed',
      confirmations: result.confirmations,
      txHashSubmitted: true,
    })
  } catch (error) {
    console.error('[Crypto] Confirm error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
