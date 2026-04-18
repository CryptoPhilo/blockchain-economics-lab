'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTranslations, useLocale } from 'next-intl'
import { useState } from 'react'
import { localeNames, type Locale } from '@/i18n/config'

export default function Header() {
  const t = useTranslations('common')
  const locale = useLocale() as Locale
  const pathname = usePathname()
  const [langOpen, setLangOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  function switchLocale(newLocale: string) {
    const segments = pathname.split('/')
    // Replace locale segment or add it
    if (['en','ko','fr','es','de','ja','zh'].includes(segments[1])) {
      segments[1] = newLocale
    } else {
      segments.splice(1, 0, newLocale)
    }
    // eslint-disable-next-line react-hooks/immutability
    window.location.href = segments.join('/') || '/'
  }

  const navItems = [
    { href: `/${locale}/reports`, label: t('reports') },
    { href: `/${locale}/alerts`, label: locale === 'ko' ? '급변동 종목' : 'Alerts' },
    { href: `/${locale}/score`, label: t('score') },
    { href: `/${locale}/products`, label: t('products') },
    { href: `/${locale}/subscribe`, label: t('newsletter') },
    { href: `/${locale}/dashboard`, label: t('dashboard') },
  ]

  return (
    <header className="sticky top-0 z-50 bg-gray-950/80 backdrop-blur-xl border-b border-white/5">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href={`/${locale}`} className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm">
            B
          </div>
          <span className="font-bold text-lg hidden sm:block">{t('siteName')}</span>
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-8">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-3">
          {/* Language Selector */}
          <div className="relative">
            <button
              onClick={() => setLangOpen(!langOpen)}
              className="px-3 py-1.5 text-sm text-gray-400 hover:text-white bg-white/5 rounded-lg border border-white/10 transition-colors"
            >
              {localeNames[locale]}
            </button>
            {langOpen && (
              <div className="absolute right-0 mt-2 w-40 bg-gray-900 border border-white/10 rounded-xl shadow-xl overflow-hidden z-50">
                {Object.entries(localeNames).map(([code, name]) => (
                  <button
                    key={code}
                    onClick={() => { switchLocale(code); setLangOpen(false) }}
                    className={`w-full px-4 py-2.5 text-sm text-left hover:bg-white/5 transition-colors ${
                      code === locale ? 'text-indigo-400 bg-indigo-500/10' : 'text-gray-300'
                    }`}
                  >
                    {name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Sign In */}
          <Link
            href={`/${locale}/auth`}
            className="px-4 py-1.5 text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors"
          >
            {t('signIn')}
          </Link>

          {/* Mobile Menu Toggle */}
          <button onClick={() => setMenuOpen(!menuOpen)} className="md:hidden text-gray-400 hover:text-white">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {menuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile Nav */}
      {menuOpen && (
        <nav className="md:hidden border-t border-white/5 bg-gray-950 px-6 py-4 space-y-3">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMenuOpen(false)}
              className="block text-gray-400 hover:text-white transition-colors"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  )
}
