import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'

interface ForensicAlert {
  id: string
  slug: string
  symbol: string
  change_24h: number
  project_id: string
}

export default async function ForensicTickerBar() {
  let formattedAlerts: ForensicAlert[] = []

  try {
    const supabase = await createServerSupabaseClient()

    const { data: alerts, error } = await supabase
      .from('project_reports')
      .select(
        `
        id,
        project_id,
        card_data,
        tracked_projects!inner(
          slug,
          symbol
        )
      `
      )
      .eq('report_type', 'forensic')
      .in('status', ['published', 'coming_soon'])
      .not('card_data', 'is', null)
      .order('published_at', { ascending: false })
      .limit(20)

    if (error || !alerts || alerts.length === 0) {
      return null
    }

    formattedAlerts = alerts
      .filter(
        (alert) => alert.tracked_projects !== null && alert.card_data !== null
      )
      .map((alert) => {
        const tp = Array.isArray(alert.tracked_projects)
          ? alert.tracked_projects[0]
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          : (alert.tracked_projects as any)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const cd = alert.card_data as Record<string, any>
        return {
          id: alert.id,
          slug: tp?.slug ?? '',
          symbol: tp?.symbol ?? '',
          change_24h: cd?.price_change_24h ?? cd?.change_24h ?? 0,
          project_id: alert.project_id,
        }
      })
  } catch (error) {
    console.error('[ForensicTickerBar] Error fetching alerts:', error)
    return null
  }

  if (formattedAlerts.length === 0) {
    return null
  }

  // Double the items for seamless scrolling
  const scrollItems = [...formattedAlerts, ...formattedAlerts]

  return (
    <div className="w-full bg-red-950/50 border-b border-red-900/30 overflow-hidden">
      <style>{`
        @keyframes forensic-scroll {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(-50%);
          }
        }
        .forensic-ticker {
          animation: forensic-scroll 30s linear infinite;
        }
        .forensic-ticker:hover {
          animation-play-state: paused;
        }
      `}</style>
      <div className="forensic-ticker flex whitespace-nowrap py-2">
        {scrollItems.map((alert, idx) => (
          <Link
            key={`${alert.id}-${idx}`}
            href={`/reports?type=forensic&project=${alert.slug}`}
            className="inline-flex items-center gap-2 px-6 py-2 hover:bg-red-900/20 transition-colors text-sm text-red-400 hover:text-red-300"
          >
            <span>⚠ {alert.symbol}</span>
            <span className={alert.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}>
              {alert.change_24h >= 0 ? '+' : ''}
              {alert.change_24h.toFixed(2)}%
            </span>
            <span className="text-red-900/50">|</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
