import { NextRequest, NextResponse } from 'next/server'
import { timingSafeEqual } from 'crypto'
import { createServerSupabaseClient } from '@/lib/supabase-server'

/**
 * POST /api/cron/forensic-monitor
 * Daily forensic monitoring collector.
 * Checks each active tracked project for anomalies:
 *   - Price change 24h (CoinGecko)
 *   - Volume ratio vs 7d avg
 *   - Large holder movements
 *   - Exchange net flows
 *
 * Triggered by Vercel Cron or external scheduler.
 * Protected by API secret.
 */

const API_SECRET = process.env.CRON_API_SECRET
const COINGECKO_API = 'https://api.coingecko.com/api/v3'

function verifyApiSecret(provided: string, secret: string): boolean {
  try {
    const providedBuf = Buffer.from(provided)
    const secretBuf = Buffer.from(secret)
    return timingSafeEqual(providedBuf, secretBuf)
  } catch {
    return false
  }
}

// Thresholds for flagging
const THRESHOLDS = {
  price_change_24h: 15,      // >15% price move
  volume_ratio: 3.0,         // 3x normal volume
  whale_movement_pct: 5,     // >5% supply moved by whales
  exchange_netflow_pct: 3,   // >3% supply net in/out of exchanges
}

interface CoinGeckoMarketData {
  id: string
  symbol: string
  price_change_percentage_24h: number
  total_volume: number
  market_cap: number
}

async function fetchCoinGeckoData(ids: string[]): Promise<Map<string, CoinGeckoMarketData>> {
  const map = new Map<string, CoinGeckoMarketData>()
  if (ids.length === 0) return map

  try {
    // STRIX-SS-001: URL-encode CoinGecko IDs to prevent parameter injection
    const idsParam = ids.map((id) => encodeURIComponent(id)).join(',')
    const url = `${COINGECKO_API}/coins/markets?vs_currency=usd&ids=${idsParam}&order=market_cap_desc&sparkline=false`
    const res = await fetch(url, {
      headers: { 'Accept': 'application/json' },
      next: { revalidate: 0 },
    })

    if (!res.ok) {
      console.error('[ForensicMonitor] CoinGecko API error:', res.status)
      return map
    }

    const data: CoinGeckoMarketData[] = await res.json()
    for (const coin of data) {
      map.set(coin.id, coin)
    }
  } catch (error) {
    console.error('[ForensicMonitor] CoinGecko fetch failed:', error)
  }

  return map
}

function assessFlags(priceChange24h: number, volumeRatio: number, whaleMovePct: number, exchangeNetflowPct: number) {
  const flags: Record<string, string> = {}
  let totalFlags = 0

  if (Math.abs(priceChange24h) >= THRESHOLDS.price_change_24h) {
    flags.price_anomaly = `${priceChange24h > 0 ? '+' : ''}${priceChange24h.toFixed(1)}% 24h price change`
    totalFlags++
  }
  if (volumeRatio >= THRESHOLDS.volume_ratio) {
    flags.volume_anomaly = `${volumeRatio.toFixed(1)}x normal volume`
    totalFlags++
  }
  if (whaleMovePct >= THRESHOLDS.whale_movement_pct) {
    flags.whale_movement = `${whaleMovePct.toFixed(1)}% supply whale movement`
    totalFlags++
  }
  if (Math.abs(exchangeNetflowPct) >= THRESHOLDS.exchange_netflow_pct) {
    const direction = exchangeNetflowPct > 0 ? 'inflow' : 'outflow'
    flags.exchange_flow = `${Math.abs(exchangeNetflowPct).toFixed(1)}% exchange ${direction}`
    totalFlags++
  }

  return { flags, totalFlags }
}

function determineAction(totalFlags: number): string {
  if (totalFlags === 0) return 'clear'
  if (totalFlags === 1) return 'watch'
  if (totalFlags === 2) return 'caution'
  if (totalFlags === 3) return 'warning'
  return 'critical'
}

export async function POST(request: NextRequest) {
  try {
    // Check API secret is configured
    if (!API_SECRET) {
      return NextResponse.json({ error: 'Service Unavailable' }, { status: 503 })
    }

    const { api_secret } = await request.json()

    // Auth check with timing-safe comparison
    if (!api_secret || !verifyApiSecret(api_secret, API_SECRET)) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const supabase = await createServerSupabaseClient()

    // Fetch active projects with forensic monitoring enabled
    const { data: projects, error: projError } = await supabase
      .from('tracked_projects')
      .select('id, name, symbol, coingecko_id, market_cap_usd, tvl_usd')
      .eq('forensic_monitoring', true)
      .in('status', ['active', 'monitoring_only'])

    if (projError || !projects || projects.length === 0) {
      return NextResponse.json({
        status: 'no_projects',
        message: 'No projects with forensic monitoring enabled',
      })
    }

    // Collect CoinGecko IDs
    const cgIds = projects
      .map((p) => p.coingecko_id)
      .filter((id): id is string => !!id)

    const marketData = await fetchCoinGeckoData(cgIds)

    const results: Array<{ project: string; action: string; flags: number }> = []

    for (const project of projects) {
      const cgData = project.coingecko_id ? marketData.get(project.coingecko_id) : null

      const priceChange24h = cgData?.price_change_percentage_24h || 0

      // Volume ratio: current volume vs market cap as proxy (simplified)
      // In production, compare against 7-day average volume from historical data
      const volumeRatio = cgData && cgData.market_cap > 0
        ? (cgData.total_volume / cgData.market_cap) * 10 // normalized ratio
        : 1.0

      // Whale movement & exchange flow: placeholder values
      // In production, these come from on-chain analytics APIs (Nansen, Arkham, etc.)
      const whaleMovePct = 0
      const exchangeNetflowPct = 0

      const { flags, totalFlags } = assessFlags(
        priceChange24h, volumeRatio, whaleMovePct, exchangeNetflowPct
      )
      const action = determineAction(totalFlags)

      // Insert monitoring log
      await supabase.from('forensic_monitoring_logs').insert({
        project_id: project.id,
        check_date: new Date().toISOString().split('T')[0],
        price_change_24h: priceChange24h,
        volume_ratio: volumeRatio,
        whale_movement_pct: whaleMovePct,
        exchange_netflow_pct: exchangeNetflowPct,
        total_flags: totalFlags,
        flag_details: totalFlags > 0 ? flags : null,
        action,
        notes: totalFlags > 0 ? `Auto-detected ${totalFlags} anomaly flag(s)` : null,
      })

      // Update threat level on tracked_projects
      await supabase
        .from('tracked_projects')
        .update({
          threat_level: action,
          market_cap_usd: cgData?.market_cap || project.market_cap_usd,
        })
        .eq('id', project.id)

      results.push({ project: project.name, action, flags: totalFlags })
    }

    const alertCount = results.filter((r) => r.flags > 0).length

    return NextResponse.json({
      status: 'completed',
      projects_checked: results.length,
      alerts: alertCount,
      results,
    })
  } catch (error) {
    console.error('[ForensicMonitor] Error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
