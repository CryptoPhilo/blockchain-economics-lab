import Stripe from 'stripe'
import { loadStripe } from '@stripe/stripe-js'

// Stripe is currently disabled (crypto-only payments)
// Initialize only if keys are available
export const stripe = process.env.STRIPE_SECRET_KEY
  ? new Stripe(process.env.STRIPE_SECRET_KEY, {
      apiVersion: '2026-03-25.dahlia' as any,
    })
  : null

let stripePromise: ReturnType<typeof loadStripe>
export function getStripe() {
  if (!stripePromise && process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY) {
    stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY)
  }
  return stripePromise
}
