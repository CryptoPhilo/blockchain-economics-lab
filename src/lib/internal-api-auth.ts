import { timingSafeEqual } from 'crypto'
import type { NextRequest } from 'next/server'

function isTruthy(value: string | undefined) {
  if (!value) return false
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase())
}

function safeCompare(provided: string, expected: string) {
  try {
    const left = Buffer.from(provided)
    const right = Buffer.from(expected)

    if (left.length !== right.length) {
      return false
    }

    return timingSafeEqual(left, right)
  } catch {
    return false
  }
}

export function getInternalApiSecret() {
  return process.env.BETA_SIGNAL_INTERNAL_API_SECRET
}

export function isPublicDeploymentEnvironment() {
  if (process.env.VERCEL === '1') return true

  const vercelEnv = process.env.VERCEL_ENV
  if (vercelEnv === 'preview' || vercelEnv === 'production') {
    return true
  }

  const publicUrl = process.env.VERCEL_URL || process.env.NEXT_PUBLIC_SITE_URL || process.env.SITE_URL
  return Boolean(publicUrl && process.env.NODE_ENV !== 'development')
}

export function isInternalApiRouteEnabled() {
  if (isTruthy(process.env.BETA_SIGNAL_INTERNAL_API_ALLOW_PUBLIC)) {
    return true
  }

  return !isPublicDeploymentEnvironment()
}

export function isAuthorizedInternalApiRequest(request: NextRequest, secret: string) {
  const authorization = request.headers.get('authorization')
  const bearer = authorization?.startsWith('Bearer ')
    ? authorization.slice('Bearer '.length).trim()
    : null
  const headerSecret = request.headers.get('x-internal-api-key')
  const candidate = bearer || headerSecret

  if (!candidate) {
    return false
  }

  return safeCompare(candidate, secret)
}
