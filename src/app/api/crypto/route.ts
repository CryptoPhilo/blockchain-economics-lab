import { NextRequest, NextResponse } from 'next/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { calculateCryptoAmount, SUPPORTED_CRYPTOS, type CryptoCurrency } from '@/lib/crypto-payments'

export async function POST(request: NextRequest) {
  try {
    const { productId, currency } = await request.json()

    if (!SUPPORTED_CRYPTOS[currency as CryptoCurrency]) {
      return NextResponse.json({ error: 'Unsupported cryptocurrency' }, { status: 400 })
    }

    const supabase = await createServerSupabaseClient()

    // Get product
    const { data: product, error } = await supabase
      .from('products')
      .select('*')
      .eq('id', productId)
      .single()

    if (error || !product) {
      return NextResponse.json({ error: 'Product not found' }, { status: 404 })
    }

    // Get current user
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 })
    }

    // Calculate crypto amount
    const cryptoConfig = SUPPORTED_CRYPTOS[currency as CryptoCurrency]
    const { amount, price } = await calculateCryptoAmount(product.price_usd_cents, currency as CryptoCurrency)

    // Create order record
    const { data: order, error: orderError } = await supabase
      .from('orders')
      .insert({
        user_id: user.id,
        status: 'pending',
        payment_method: `crypto_${currency.toLowerCase()}`,
        subtotal_cents: product.price_usd_cents,
        total_cents: product.price_usd_cents,
        crypto_amount: amount,
        crypto_currency: currency,
        crypto_wallet_address: cryptoConfig.receivingAddress,
      })
      .select()
      .single()

    if (orderError) {
      console.error('Order creation error:', orderError)
      return NextResponse.json({ error: 'Failed to create order' }, { status: 500 })
    }

    // Create order item
    await supabase.from('order_items').insert({
      order_id: order.id,
      product_id: product.id,
      unit_price_cents: product.price_usd_cents,
    })

    // Create crypto payment tracking record
    const expiresAt = new Date(Date.now() + 30 * 60 * 1000) // 30 min expiry
    await supabase.from('crypto_payments').insert({
      order_id: order.id,
      currency: currency,
      network: cryptoConfig.network,
      amount: amount,
      receiving_address: cryptoConfig.receivingAddress,
      required_confirmations: cryptoConfig.requiredConfirmations,
      expires_at: expiresAt.toISOString(),
    })

    return NextResponse.json({
      orderId: order.id,
      amount,
      address: cryptoConfig.receivingAddress,
      currency,
      network: cryptoConfig.network,
      price,
      expiresAt: expiresAt.toISOString(),
    })
  } catch (err: any) {
    console.error('Crypto payment error:', err)
    return NextResponse.json({ error: err.message }, { status: 500 })
  }
}
