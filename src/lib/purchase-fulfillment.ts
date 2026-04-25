import type { SupabaseClient } from '@supabase/supabase-js'
import type { PaymentMethod, Product } from '@/lib/types'

interface FulfillOrderOptions {
  supabase: SupabaseClient
  orderId: string
  userId: string
  paymentMethod: PaymentMethod
  paidAt?: string
  stripeSubscriptionId?: string | null
}

function computeSubscriptionPeriodEnd(product: Pick<Product, 'subscription_interval'>, referenceDate: Date) {
  const next = new Date(referenceDate)
  next.setUTCMonth(next.getUTCMonth() + (product.subscription_interval === 'yearly' ? 12 : 1))
  return next.toISOString()
}

async function upsertSubscriptionAccess(args: {
  supabase: SupabaseClient
  userId: string
  product: Product
  paymentMethod: PaymentMethod
  paidAt: string
  orderId: string
  stripeSubscriptionId?: string | null
}) {
  const { supabase, userId, product, paymentMethod, paidAt, stripeSubscriptionId } = args
  const accessExpiresAt = computeSubscriptionPeriodEnd(product, new Date(paidAt))

  const existingSubscriptions = await supabase
    .from('subscriptions')
    .select('id')
    .eq('user_id', userId)
    .eq('product_id', product.id)
    .in('status', ['active', 'trialing'])
    .order('created_at', { ascending: false })
    .limit(1)

  if (existingSubscriptions.error) {
    throw new Error(`Failed to query subscriptions: ${existingSubscriptions.error.message}`)
  }

  const existingSubscription = existingSubscriptions.data?.[0]

  if (existingSubscription) {
    const { error } = await supabase
      .from('subscriptions')
      .update({
        status: 'active',
        payment_method: paymentMethod,
        current_period_start: paidAt,
        current_period_end: accessExpiresAt,
        ...(stripeSubscriptionId ? { stripe_subscription_id: stripeSubscriptionId } : {}),
      })
      .eq('id', existingSubscription.id)

    if (error) {
      throw new Error(`Failed to update subscription: ${error.message}`)
    }

    return { subscriptionId: existingSubscription.id, accessExpiresAt }
  }

  const { data, error } = await supabase
    .from('subscriptions')
    .insert({
      user_id: userId,
      product_id: product.id,
      status: 'active',
      payment_method: paymentMethod,
      current_period_start: paidAt,
      current_period_end: accessExpiresAt,
      ...(stripeSubscriptionId ? { stripe_subscription_id: stripeSubscriptionId } : {}),
    })
    .select('id')
    .single()

  if (error) {
    throw new Error(`Failed to create subscription: ${error.message}`)
  }

  return { subscriptionId: data.id as string, accessExpiresAt }
}

async function upsertLibraryAccess(args: {
  supabase: SupabaseClient
  userId: string
  productId: string
  orderId: string
  accessGrantedAt: string
  accessExpiresAt: string | null
  subscriptionId?: string
}) {
  const { supabase, userId, productId, orderId, accessGrantedAt, accessExpiresAt, subscriptionId } = args

  const existingLibraryEntries = await supabase
    .from('user_library')
    .select('id')
    .eq('user_id', userId)
    .eq('product_id', productId)
    .order('access_granted_at', { ascending: false })
    .limit(1)

  if (existingLibraryEntries.error) {
    throw new Error(`Failed to query library access: ${existingLibraryEntries.error.message}`)
  }

  const existingEntry = existingLibraryEntries.data?.[0]
  const payload = {
    order_id: orderId,
    subscription_id: subscriptionId ?? null,
    access_granted_at: accessGrantedAt,
    access_expires_at: accessExpiresAt,
  }

  if (existingEntry) {
    const { error } = await supabase
      .from('user_library')
      .update(payload)
      .eq('id', existingEntry.id)

    if (error) {
      throw new Error(`Failed to update library access: ${error.message}`)
    }

    return
  }

  const { error } = await supabase
    .from('user_library')
    .insert({
      user_id: userId,
      product_id: productId,
      download_count: 0,
      ...payload,
    })

  if (error) {
    throw new Error(`Failed to create library access: ${error.message}`)
  }
}

export async function fulfillOrderEntitlements({
  supabase,
  orderId,
  userId,
  paymentMethod,
  paidAt = new Date().toISOString(),
  stripeSubscriptionId,
}: FulfillOrderOptions) {
  const { error: orderError } = await supabase
    .from('orders')
    .update({
      status: 'completed',
      paid_at: paidAt,
    })
    .eq('id', orderId)
    .neq('status', 'completed')

  if (orderError) {
    throw new Error(`Failed to update order: ${orderError.message}`)
  }

  const orderItemsResult = await supabase
    .from('order_items')
    .select('product:products(*)')
    .eq('order_id', orderId)

  if (orderItemsResult.error) {
    throw new Error(`Failed to fetch order items: ${orderItemsResult.error.message}`)
  }

  for (const item of orderItemsResult.data || []) {
    const product = item.product as unknown as Product | null

    if (!product) {
      continue
    }

    let subscriptionId: string | undefined
    let accessExpiresAt: string | null = null

    if (product.type === 'subscription') {
      const result = await upsertSubscriptionAccess({
        supabase,
        userId,
        product,
        paymentMethod,
        paidAt,
        orderId,
        stripeSubscriptionId,
      })

      subscriptionId = result.subscriptionId
      accessExpiresAt = result.accessExpiresAt
    }

    await upsertLibraryAccess({
      supabase,
      userId,
      productId: product.id,
      orderId,
      accessGrantedAt: paidAt,
      accessExpiresAt,
      subscriptionId,
    })
  }
}
