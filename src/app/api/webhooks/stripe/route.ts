import { NextRequest, NextResponse } from 'next/server'
import { stripe } from '@/lib/stripe'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import Stripe from 'stripe'

export async function POST(request: NextRequest) {
  const body = await request.text()
  const sig = request.headers.get('stripe-signature')!

  let event: Stripe.Event

  try {
    if (!stripe) {
      return NextResponse.json({ error: 'Stripe is not configured' }, { status: 503 })
    }
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!)
  } catch (err: any) {
    console.error('Webhook signature verification failed:', err.message)
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 })
  }

  const supabase = await createServerSupabaseClient()

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.Checkout.Session
      const { product_id, product_type, user_id } = session.metadata || {}

      if (!product_id || !user_id || user_id === 'guest') break

      // Create order
      const { data: order } = await supabase
        .from('orders')
        .insert({
          user_id,
          status: 'completed',
          payment_method: 'stripe',
          subtotal_cents: session.amount_total || 0,
          total_cents: session.amount_total || 0,
          stripe_session_id: session.id,
          stripe_payment_intent_id: session.payment_intent as string,
          paid_at: new Date().toISOString(),
        })
        .select()
        .single()

      if (order) {
        // Create order item
        await supabase.from('order_items').insert({
          order_id: order.id,
          product_id,
          unit_price_cents: session.amount_total || 0,
        })

        // Grant access to user library
        if (product_type === 'subscription') {
          // Create subscription
          await supabase.from('subscriptions').insert({
            user_id,
            product_id,
            status: 'active',
            payment_method: 'stripe',
            stripe_subscription_id: session.subscription as string,
            current_period_start: new Date().toISOString(),
            current_period_end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
          })
        }

        // Add to user library
        await supabase.from('user_library').insert({
          user_id,
          product_id,
          order_id: order.id,
          access_expires_at: product_type === 'subscription'
            ? new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
            : null,
        })
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
