function isTruthy(value: string | undefined) {
  if (!value) return false
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase())
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
