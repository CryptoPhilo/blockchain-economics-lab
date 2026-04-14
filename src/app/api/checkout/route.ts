import { NextRequest, NextResponse } from 'next/server'
import { stripe } from '@/lib/stripe'
import { createServerSupabaseClient } from '@/lib/supabase-server'

export async function POST(request: NextRequest) {
  try {
    const { productId, locale } = await request.json()
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

    // Get current user (optional - allow guest checkout)
    const { data: { user } } = await supabase.auth.getUser()

    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'

    // Create Stripe checkout session
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sessionParams: any = {
      payment_method_types: ['card'],
      line_items: [
        {
          price_data: {
            currency: 'usd',
            product_data: {
              name: product.title_en,
              description: product.description_en?.substring(0, 200) || undefined,
            },
            unit_amount: product.price_usd_cents,
            ...(product.type === 'subscription' && {
              recurring: {
                interval: product.subscription_interval === 'yearly' ? 'year' : 'month',
              },
            }),
          },
          quantity: 1,
        },
      ],
      mode: product.type === 'subscription' ? 'subscription' : 'payment',
      success_url: `${baseUrl}/${locale}/dashboard?success=true&session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${baseUrl}/${locale}/products/${product.slug}?cancelled=true`,
      metadata: {
        product_id: product.id,
        product_type: product.type,
        user_id: user?.id || 'guest',
      },
    }

    if (user?.email) {
      sessionParams.customer_email = user.email
    }

    if (!stripe) {
      return NextResponse.json({ error: 'Stripe is not configured. Use crypto payments.' }, { status: 503 })
    }
    const session = await stripe.checkout.sessions.create(sessionParams)

    return NextResponse.json({ url: session.url })
  } catch (err) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const error = err as any
    console.error('Checkout error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
