import createMiddleware from 'next-intl/middleware'
import { locales, defaultLocale } from './i18n/config'

export default createMiddleware({
  locales,
  defaultLocale,
  localePrefix: 'always',
})

export const config = {
  matcher: ['/', '/(en|ko|fr|es|de|ja|zh)/:path*', '/((?!api|_next|_vercel|.*\\..*).*)'],
}
