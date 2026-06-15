'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTranslations, useLocale } from 'next-intl'
import { useState } from 'react'
import { localeNames, type Locale } from '@/i18n/config'
import BrandMark from './BrandMark'

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
    { href: `/${locale}/score`, label: t('score') },
    { href: `/${locale}/exchanges`, label: t('exchanges') },
  ]

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/[0.88] backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Logo */}
        <Link href={`/${locale}`} className="flex items-center gap-3">
          <BrandMark />
          <span className="hidden leading-none sm:block">
            <span className="block text-[15px] font-semibold tracking-wide text-white">BCE Lab</span>
            <span className="mt-1 block text-[10px] font-medium uppercase tracking-[0.24em] text-slate-500">
              {t('siteName')}
            </span>
          </span>
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm font-medium text-slate-400 transition-colors hover:bg-white/[0.04] hover:text-white"
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
              className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-1.5 text-sm font-medium text-slate-300 transition-colors hover:border-cyan-300/30 hover:text-white"
            >
              {localeNames[locale]}
            </button>
            {langOpen && (
              <div className="absolute right-0 z-50 mt-2 w-40 overflow-hidden rounded-lg border border-white/10 bg-slate-950 shadow-2xl shadow-black/50">
                {Object.entries(localeNames).map(([code, name]) => (
                  <button
                    key={code}
                    onClick={() => { switchLocale(code); setLangOpen(false) }}
                    className={`w-full px-4 py-2.5 text-left text-sm transition-colors hover:bg-white/[0.06] ${
                      code === locale ? 'bg-cyan-400/10 text-cyan-200' : 'text-slate-300'
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
            className="rounded-md bg-white px-4 py-1.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-100"
          >
            {t('signIn')}
          </Link>

          {/* Mobile Menu Toggle */}
          <button onClick={() => setMenuOpen(!menuOpen)} className="text-slate-400 hover:text-white md:hidden">
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
        <nav className="space-y-2 border-t border-white/10 bg-slate-950 px-6 py-4 md:hidden">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMenuOpen(false)}
              className="block rounded-md px-2 py-2 text-slate-400 transition-colors hover:bg-white/[0.04] hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  )
}
