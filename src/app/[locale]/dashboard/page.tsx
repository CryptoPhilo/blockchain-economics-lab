import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocalizedField, formatPrice, type Locale } from '@/lib/types'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import DashboardOnboarding from '@/components/DashboardOnboarding'
import ReferralTab from '@/components/ReferralTab'
import { randomBytes } from 'crypto'

export default async function DashboardPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const supabase = await createServerSupabaseClient()
  const t = await getTranslations('dashboard')

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect(`/${locale}/auth`)

  // Fetch profile for onboarding check
  const { data: profile } = await supabase
    .from('profiles')
    .select('onboarding_completed, referral_code, referred_by')
    .eq('id', user.id)
    .single()

  // Generate referral code if missing
  let referralCode = profile?.referral_code || ''
  if (!referralCode) {
    referralCode = 'BCE-' + randomBytes(3).toString('hex').toUpperCase()
    await supabase
      .from('profiles')
      .update({ referral_code: referralCode })
      .eq('id', user.id)
  }

  // OPS-011-T13: Auto-claim referral code from signup metadata
  const signupRefCode = user.user_metadata?.referral_code
  if (signupRefCode && !profile?.referred_by) {
    const code = String(signupRefCode).trim().toUpperCase()
    const { data: referrer } = await supabase
      .from('profiles')
      .select('id')
      .eq('referral_code', code)
      .single()
    if (referrer && referrer.id !== user.id) {
      const { data: existing } = await supabase
        .from('member_referrals')
        .select('id')
        .eq('referred_id', user.id)
        .maybeSingle()
      if (!existing) {
        await supabase.from('member_referrals').insert({
          referrer_id: referrer.id,
          referred_id: user.id,
          referral_code: code,
          status: 'converted',
          reward_type: 'discount',
          reward_value: 20,
        })
        await supabase
          .from('profiles')
          .update({ referred_by: referrer.id })
          .eq('id', user.id)
      }
    }
  }

  const needsOnboarding = profile && !profile.onboarding_completed

  // Fetch user's library
  const { data: library } = await supabase
    .from('user_library')
    .select('*, product:products(*)')
    .eq('user_id', user.id)
    .order('access_granted_at', { ascending: false })

  // Fetch active subscriptions
  const { data: subscriptions } = await supabase
    .from('subscriptions')
    .select('*, product:products(*)')
    .eq('user_id', user.id)
    .eq('status', 'active')

  // Fetch order history
  const { data: orders } = await supabase
    .from('orders')
    .select('*, items:order_items(*, product:products(*))')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })
    .limit(10)

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* OPS-011-T08: Onboarding modal for new members */}
      {needsOnboarding && (
        <DashboardOnboarding userId={user.id} referralCode={referralCode} locale={locale} />
      )}

      <h1 className="text-3xl font-bold mb-10">{t('title')}</h1>

      {/* Active Subscriptions */}
      {subscriptions && subscriptions.length > 0 && (
        <section className="mb-12">
          <h2 className="text-xl font-semibold mb-4">{t('mySubscriptions')}</h2>
          <div className="grid gap-4">
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {subscriptions.map((sub: any) => (
              <div key={sub.id} className="p-5 rounded-xl bg-green-500/5 border border-green-500/20 flex items-center justify-between">
                <div>
                  <h3 className="font-semibold">{getLocalizedField(sub.product, 'title', locale as Locale)}</h3>
                  <p className="text-sm text-gray-500">
                    {t('expiresOn', { date: new Date(sub.current_period_end).toLocaleDateString() })}
                  </p>
                </div>
                <span className="px-3 py-1 rounded-full bg-green-500/20 text-green-400 text-sm font-medium">
                  {t('activeSubscription')}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Library */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold mb-4">{t('myLibrary')}</h2>
        {library && library.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {library.map((item: any) => (
              <div key={item.id} className="p-5 rounded-xl bg-white/5 border border-white/5">
                <h3 className="font-semibold mb-2">{getLocalizedField(item.product, 'title', locale as Locale)}</h3>
                <p className="text-sm text-gray-500 mb-4 line-clamp-2">
                  {getLocalizedField(item.product, 'description', locale as Locale)}
                </p>
                <div className="flex gap-2">
                  <a
                    href={`/api/reports/${item.product?.id || item.product_id}?lang=${locale}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    {t('viewReport')}
                  </a>
                  <a
                    href={`/api/reports/${item.product?.id || item.product_id}?lang=${locale}&download=true`}
                    className="px-4 py-2 bg-white/5 hover:bg-white/10 text-white text-sm font-medium rounded-lg border border-white/10 transition-colors"
                  >
                    {t('downloadReport')}
                  </a>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 text-gray-500 bg-white/[0.02] rounded-xl border border-white/5">
            <p className="mb-4">{t('noReports')}</p>
            <Link href={`/${locale}/products`} className="text-indigo-400 hover:text-indigo-300">
              Browse Reports →
            </Link>
          </div>
        )}
      </section>

      {/* Referral Program — OPS-011-T13 */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold mb-4">{t('myReferrals')}</h2>
        <ReferralTab locale={locale} referralCode={referralCode} />
      </section>

      {/* Order History */}
      <section>
        <h2 className="text-xl font-semibold mb-4">{t('orderHistory')}</h2>
        {orders && orders.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-white/5">
                  <th className="pb-3 font-medium">Date</th>
                  <th className="pb-3 font-medium">Items</th>
                  <th className="pb-3 font-medium">Payment</th>
                  <th className="pb-3 font-medium">Amount</th>
                  <th className="pb-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                {orders.map((order: any) => (
                  <tr key={order.id} className="border-b border-white/5">
                    <td className="py-3 text-gray-400">{new Date(order.created_at).toLocaleDateString()}</td>
                    <td className="py-3">
                      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                      {order.items?.map((item: any) => (
                        <span key={item.id}>{getLocalizedField(item.product, 'title', locale as Locale)}</span>
                      ))}
                    </td>
                    <td className="py-3 text-gray-400">{order.payment_method === 'stripe' ? '💳 Card' : `🔗 ${order.crypto_currency || 'Crypto'}`}</td>
                    <td className="py-3 text-white font-medium">{formatPrice(order.total_cents)}</td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        order.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                        order.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-red-500/20 text-red-400'
                      }`}>
                        {order.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-center py-8">No orders yet.</p>
        )}
      </section>
    </div>
  )
}
