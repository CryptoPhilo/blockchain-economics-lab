'use client'

import Link from 'next/link'
import { useTranslations, useLocale } from 'next-intl'
import BrandMark from './BrandMark'

export default function Footer() {
  const t = useTranslations('footer')
  const common = useTranslations('common')
  const locale = useLocale()

  return (
    <footer className="bg-gray-950 border-t border-white/5 mt-20">
      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          {/* Brand */}
          <div className="md:col-span-2">
            <div className="mb-4 flex items-center gap-3">
              <BrandMark />
              <span className="leading-none">
                <span className="block text-[15px] font-semibold tracking-wide text-white">BCE Lab</span>
                <span className="mt-1 block text-[10px] font-medium uppercase tracking-[0.24em] text-slate-500">
                  {common('siteName')}
                </span>
              </span>
            </div>
            <p className="text-gray-500 text-sm leading-relaxed max-w-md">{t('aboutText')}</p>
          </div>

          {/* Research */}
          <div>
            <h4 className="font-semibold text-white mb-4">{t('research')}</h4>
            <ul className="space-y-2.5 text-sm text-gray-500">
              <li><Link href={`/${locale}/reports`} className="hover:text-gray-300 transition-colors">Rapid Change Items</Link></li>
              <li><Link href={`/${locale}/score`} className="hover:text-gray-300 transition-colors">Report Rankings</Link></li>
              <li><Link href={`/${locale}/free-reports`} className="hover:text-gray-300 transition-colors">Free Reports</Link></li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="font-semibold text-white mb-4">{t('legal')}</h4>
            <ul className="space-y-2.5 text-sm text-gray-500">
              <li><Link href={`/${locale}/privacy`} className="hover:text-gray-300 transition-colors">{t('privacy')}</Link></li>
              <li><Link href={`/${locale}/terms`} className="hover:text-gray-300 transition-colors">{t('terms')}</Link></li>
              <li><Link href={`/${locale}/contact`} className="hover:text-gray-300 transition-colors">{t('contact')}</Link></li>
            </ul>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="mt-10 pt-8 border-t border-white/5">
          <p className="text-xs text-gray-600 leading-relaxed text-center max-w-3xl mx-auto">
            <strong className="text-gray-500">Disclaimer:</strong>{' '}
            This content is produced by Blockchain Economics Lab for informational and educational purposes only.
            It does not constitute financial, investment, or trading advice. Cryptocurrency markets carry significant risk.
            Users are solely responsible for their own trading decisions.
          </p>
        </div>

        <div className="mt-6 pt-4 border-t border-white/5 text-center text-sm text-gray-600">
          {t('copyright')}
        </div>
      </div>
    </footer>
  )
}
