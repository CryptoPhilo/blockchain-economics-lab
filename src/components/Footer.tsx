'use client'

import Link from 'next/link'
import { useTranslations, useLocale } from 'next-intl'

function BceLabMark() {
  return (
    <span className="relative flex h-9 w-9 items-center justify-center overflow-hidden rounded-md border border-cyan-300/25 bg-slate-950 shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_12px_30px_rgba(14,165,233,0.18)]">
      <svg viewBox="0 0 36 36" aria-hidden="true" className="h-8 w-8">
        <path d="M10 28V8h9.2c4.1 0 6.7 2 6.7 5.1 0 1.8-.9 3.2-2.5 4 2.2.7 3.6 2.4 3.6 4.8 0 3.7-2.9 6.1-7.4 6.1H10Z" fill="#f8fafc" />
        <path d="M14.5 16h4.1c1.5 0 2.4-.7 2.4-1.9 0-1.1-.9-1.8-2.4-1.8h-4.1V16Zm0 7.7h4.8c1.7 0 2.7-.8 2.7-2.1 0-1.4-1-2.2-2.8-2.2h-4.7v4.3Z" fill="#020617" />
        <circle cx="27.5" cy="8.5" r="2.2" fill="#22d3ee" />
        <circle cx="28.5" cy="27.5" r="2.2" fill="#34d399" />
        <path d="M25.8 10.2 22.8 14M23.6 22.7l3.2 3.1" stroke="#38bdf8" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    </span>
  )
}

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
              <BceLabMark />
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
