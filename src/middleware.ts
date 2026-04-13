import createMiddleware from 'next-intl/middleware'
import { NextRequest, NextResponse } from 'next/server'
import { locales, defaultLocale } from './i18n/config'

const RESTRICTED_COUNTRIES = ['KR']

const intlMiddleware = createMiddleware({
  locales,
  defaultLocale,
  localePrefix: 'always',
})

export default function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Skip API routes, Next.js internals, and static files
  if (
    pathname.startsWith('/api') ||
    pathname.startsWith('/_next') ||
    pathname.startsWith('/_vercel') ||
    pathname.includes('.')
  ) {
    // For API routes, add geo headers
    if (pathname.startsWith('/api/referral')) {
      const country = request.headers.get('x-vercel-ip-country') || ''
      const isRestricted = RESTRICTED_COUNTRIES.includes(country)
      const response = NextResponse.next()
      response.headers.set('x-geo-restricted', isRestricted ? '1' : '0')
      response.headers.set('x-geo-country', country)
      return response
    }
    return NextResponse.next()
  }

  // Geo-compliance: detect country for all locale pages
  const country = request.headers.get('x-vercel-ip-country') || ''
  const isRestricted = RESTRICTED_COUNTRIES.includes(country)

  // Check if pathname already has a locale prefix
  const pathnameHasLocale = locales.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
  )

  // If no locale prefix, redirect to default locale
  if (!pathnameHasLocale && pathname !== '/') {
    const url = request.nextUrl.clone()
    url.pathname = `/${defaultLocale}${pathname}`
    return NextResponse.redirect(url)
  }

  const response = intlMiddleware(request)

  // Inject geo headers into all locale page responses
  response.headers.set('x-geo-restricted', isRestricted ? '1' : '0')
  response.headers.set('x-geo-country', country)

  return response
}

export const config = {
  matcher: ['/((?!_next|_vercel|.*\\..*).*)', '/'],
}
