import { NextRequest, NextResponse } from 'next/server'
import Stripe from 'stripe'
import { stripe } from '@/lib/stripe'
import { createSupabaseAdminClient } from '@/lib/supabase-admin'
import { fulfillOrderEntitlements } from '@/lib/purchase-fulfillment'
import { isProductPubliclyAvailable } from '@/lib/product-access'

export async function POST(request: NextRequest) {
  const body = await request.text()
  const sig = request.headers.get('stripe-signature')!

  let event: Stripe.Event

  try {
    if (!stripe) {
      return NextResponse.json({ error: 'Stripe is not configured' }, { status: 503 })
    }

    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown signature error'
    console.error('Webhook signature verification failed:', message)
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 })
  }

  const supabase = createSupabaseAdminClient()

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.Checkout.Session
      const { product_id, user_id } = session.metadata || {}

      if (!product_id || !user_id || user_id === 'guest') {
        break
      }

      const { data: product } = await supabase
        .from('products')
        .select('*')
        .eq('id', product_id)
        .single()

      if (!product || !isProductPubliclyAvailable(product)) {
        console.error(`[Stripe Webhook] Product not found: ${product_id}`)
        break
      }

      const paidAmount = session.amount_total || 0
      if (paidAmount < product.price_usd_cents) {
        console.error(
          `[Stripe Webhook] PRICE MISMATCH: paid=${paidAmount} expected=${product.price_usd_cents} ` +
          `product=${product_id} session=${session.id} user=${user_id}`
        )
        break
      }

      const existingOrders = await supabase
        .from('orders')
        .select('id')
        .eq('stripe_session_id', session.id)
        .order('created_at', { ascending: false })
        .limit(1)

      if (existingOrders.error) {
        console.error('[Stripe Webhook] Failed to query existing orders:', existingOrders.error.message)
        break
      }

      let orderId = existingOrders.data?.[0]?.id as string | undefined
      const paidAt = new Date().toISOString()

      if (!orderId) {
        const { data: order, error: orderError } = await supabase
          .from('orders')
          .insert({
            user_id,
            status: 'completed',
            payment_method: 'stripe',
            subtotal_cents: paidAmount,
            total_cents: paidAmount,
            stripe_session_id: session.id,
            stripe_payment_intent_id: session.payment_intent as string,
            paid_at: paidAt,
          })
          .select('id')
          .single()

        if (orderError || !order) {
          console.error('[Stripe Webhook] Failed to create order:', orderError?.message)
          break
        }

        orderId = order.id as string

        const { error: orderItemError } = await supabase.from('order_items').insert({
          order_id: orderId,
          product_id,
          unit_price_cents: paidAmount,
        })

        if (orderItemError) {
          console.error('[Stripe Webhook] Failed to create order item:', orderItemError.message)
          break
        }
      }

      try {
        await fulfillOrderEntitlements({
          supabase,
          orderId,
          userId: user_id,
          paymentMethod: 'stripe',
          paidAt,
          stripeSubscriptionId: typeof session.subscription === 'string' ? session.subscription : null,
        })
      } catch (error) {
        console.error('[Stripe Webhook] Failed to fulfill entitlements:', error)
      }
      break
    }

    case 'customer.subscription.deleted': {
      const subscription = event.data.object as Stripe.Subscription
      await supabase
        .from('subscriptions')
        .update({ status: 'cancelled', cancelled_at: new Date().toISOString() })
        .eq('stripe_subscription_id', subscription.id)
      break
    }
  }

  return NextResponse.json({ received: true })
}
