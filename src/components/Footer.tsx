'use client'

import Link from 'next/link'
import { useTranslations, useLocale } from 'next-intl'

export default function Footer() {
  const t = useTranslations('footer')
  const locale = useLocale()

  return (
    <footer className="bg-gray-950 border-t border-white/5 mt-20">
      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10">
          {/* Brand */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm">B</div>
              <span className="font-bold text-lg">Blockchain Economics Lab</span>
            </div>
            <p className="text-gray-500 text-sm leading-relaxed max-w-md">{t('aboutText')}</p>
            {/* Newsletter */}
            <div className="mt-6">
              <p className="text-sm font-medium text-gray-300 mb-3">{t('newsletter')}</p>
              <div className="flex gap-2">
                <input
                  type="email"
                  placeholder={t('emailPlaceholder')}
                  className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                />
                <button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors">
                  {t('subscribeBtn')}
                </button>
              </div>
            </div>
          </div>

          {/* Research */}
          <div>
            <h4 className="font-semibold text-white mb-4">{t('research')}</h4>
            <ul className="space-y-2.5 text-sm text-gray-500">
              <li><Link href={`/${locale}/products?category=onchain-analytics`} className="hover:text-gray-300 transition-colors">On-Chain Analytics</Link></li>
              <li><Link href={`/${locale}/products?category=tokenomics`} className="hover:text-gray-300 transition-colors">Tokenomics</Link></li>
              <li><Link href={`/${locale}/products?category=defi`} className="hover:text-gray-300 transition-colors">DeFi Research</Link></li>
              <li><Link href={`/${locale}/products?category=macro-crypto`} className="hover:text-gray-300 transition-colors">Macro & Crypto</Link></li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="font-semibold text-white mb-4">{t('legal')}</h4>
            <ul className="space-y-2.5 text-sm text-gray-500">
              <li><Link href="#" className="hover:text-gray-300 transition-colors">{t('privacy')}</Link></li>
              <li><Link href="#" className="hover:text-gray-300 transition-colors">{t('terms')}</Link></li>
              <li><Link href="#" className="hover:text-gray-300 transition-colors">{t('contact')}</Link></li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-white/5 text-center text-sm text-gray-600">
          {t('copyright')}
        </div>
      </div>
    </footer>
  )
}
