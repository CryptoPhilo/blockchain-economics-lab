/**
 * STRIX-INFRA-002: In-memory rate limiter for API endpoints.
 *
 * Uses a simple sliding-window approach with an in-memory Map.
 * For production at scale, replace with @upstash/ratelimit + Redis.
 *
 * Usage:
 *   const limiter = createRateLimiter({ windowMs: 60_000, max: 10 })
 *   const { success, remaining } = limiter.check(identifier)
 */

interface RateLimitConfig {
  /** Window duration in milliseconds */
  windowMs: number
  /** Maximum number of requests per window */
  max: number
}

interface RateLimitEntry {
  count: number
  resetAt: number
}

interface RateLimitResult {
  success: boolean
  remaining: number
  resetAt: number
}

class RateLimiter {
  private store = new Map<string, RateLimitEntry>()
  private config: RateLimitConfig

  constructor(config: RateLimitConfig) {
    this.config = config
    // Periodic cleanup every 5 minutes to prevent memory leaks
    if (typeof setInterval !== 'undefined') {
      setInterval(() => this.cleanup(), 5 * 60 * 1000)
    }
  }

  check(identifier: string): RateLimitResult {
    const now = Date.now()
    const entry = this.store.get(identifier)

    // New window or expired window
    if (!entry || now >= entry.resetAt) {
      this.store.set(identifier, {
        count: 1,
        resetAt: now + this.config.windowMs,
      })
      return {
        success: true,
        remaining: this.config.max - 1,
        resetAt: now + this.config.windowMs,
      }
    }

    // Within window
    if (entry.count < this.config.max) {
      entry.count++
      return {
        success: true,
        remaining: this.config.max - entry.count,
        resetAt: entry.resetAt,
      }
    }

    // Rate limited
    return {
      success: false,
      remaining: 0,
      resetAt: entry.resetAt,
    }
  }

  private cleanup() {
    const now = Date.now()
    for (const [key, entry] of this.store) {
      if (now >= entry.resetAt) {
        this.store.delete(key)
      }
    }
  }
}

export function createRateLimiter(config: RateLimitConfig): RateLimiter {
  return new RateLimiter(config)
}

// Pre-configured limiters for different endpoints
// Subscribe: 5 requests per IP per hour
export const subscribeLimiter = createRateLimiter({ windowMs: 60 * 60 * 1000, max: 5 })

// Checkout / Crypto: 10 requests per user per hour
export const paymentLimiter = createRateLimiter({ windowMs: 60 * 60 * 1000, max: 10 })

// Crypto confirm (polling): 30 requests per user per minute
export const cryptoConfirmLimiter = createRateLimiter({ windowMs: 60 * 1000, max: 30 })

// Newsletter send: 2 requests per minute (cron only)
export const cronLimiter = createRateLimiter({ windowMs: 60 * 1000, max: 2 })

// Reports: 20 requests per user per minute
export const reportsLimiter = createRateLimiter({ windowMs: 60 * 1000, max: 20 })

// General API: 60 requests per IP per minute
export const generalLimiter = createRateLimiter({ windowMs: 60 * 1000, max: 60 })

/**
 * Extract rate limit identifier from request.
 * Uses IP address (from Vercel headers) or fallback.
 */
export function getRateLimitId(request: Request, userId?: string): string {
  if (userId) return `user:${userId}`
  const forwarded = request.headers.get('x-forwarded-for')
  const ip = forwarded?.split(',')[0]?.trim() || 'unknown'
  return `ip:${ip}`
}

/**
 * Create a 429 Too Many Requests response with proper headers.
 */
export function rateLimitResponse(result: RateLimitResult) {
  return new Response(
    JSON.stringify({ error: 'Too many requests. Please try again later.' }),
    {
      status: 429,
      headers: {
        'Content-Type': 'application/json',
        'Retry-After': String(Math.ceil((result.resetAt - Date.now()) / 1000)),
        'X-RateLimit-Remaining': String(result.remaining),
        'X-RateLimit-Reset': String(Math.ceil(result.resetAt / 1000)),
      },
    }
  )
}
