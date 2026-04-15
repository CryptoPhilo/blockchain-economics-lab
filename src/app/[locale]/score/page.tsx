import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import ScoreTableGate from '@/components/ScoreTableGate'
import SubscribeForm from '@/components/SubscribeForm'

/**
 * OPS-011-T05: Maturity Score Rankings Page
 *
 * Shows the BCE Maturity Score™ leaderboard.
 * Top 20 projects are publicly visible; the rest are behind an email gate.
 * Data source: project_reports table (latest maturity reports).
 */

export default async function ScorePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t = await getTranslations()
  const supabase = await createServerSupabaseClient()

  // Fetch all published maturity reports, ordered by score
  // Each project may have multiple versions — we want the latest per project
  const { data: reports } = await supabase
    .from('project_reports')
    .select(`
      id,
      project_id,
      version,
      published_at,
      project:tracked_projects(id, name, slug, symbol, category, maturity_score)
    `)
    .eq('report_type', 'maturity')
    .eq('status', 'published')
    .order('published_at', { ascending: false })

  // Deduplicate: keep only the latest report per project
  const seenProjects = new Set<string>()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const latestReports: any[] = []
  for (const r of reports || []) {
    if (r.project_id && !seenProjects.has(r.project_id)) {
      seenProjects.add(r.project_id)
      latestReports.push(r)
    }
  }

  // Build ranked rows by maturity_score
  const rows = latestReports
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((r: any) => r.project?.maturity_score != null)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .sort((a: any, b: any) => (b.project?.maturity_score || 0) - (a.project?.maturity_score || 0))
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((r: any, i: number) => ({
      rank: i + 1,
      name: r.project.name,
      symbol: r.project.symbol,
      score: r.project.maturity_score,
      category: r.project.category || '',
    }))

  const isKo = locale === 'ko'

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-bold mb-3">{t('score.title')}</h1>
        <p className="text-gray-400 max-w-xl mx-auto">{t('score.subtitle')}</p>
      </div>

      {/* Methodology summary */}
      <div className="mb-8 p-5 rounded-xl bg-white/[0.03] border border-white/5">
        <h3 className="font-semibold text-white mb-2">{t('score.methodology')}</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-gray-400">
          {[
            { label: 'Technology', weight: '20%' },
            { label: 'Business', weight: '20%' },
            { label: 'Tokenomics', weight: '15%' },
            { label: 'Narrative', weight: '15%' },
            { label: 'Governance', weight: '10%' },
            { label: 'Community', weight: '10%' },
            { label: 'Compliance', weight: '10%' },
          ].map((axis) => (
            <div key={axis.label} className="flex justify-between px-2 py-1 rounded bg-white/5">
              <span>{axis.label}</span>
              <span className="text-indigo-400 font-mono">{axis.weight}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Score table with email gate */}
      {rows.length > 0 ? (
        <ScoreTableGate rows={rows} freeLimit={20} locale={locale} />
      ) : (
        <div className="text-center py-20">
          <p className="text-gray-500 text-lg">
            {isKo ? '아직 등급 데이터가 없습니다.' : 'No maturity scores available yet.'}
          </p>
          <p className="text-gray-600 text-sm mt-2">
            {isKo ? '첫 번째 보고서가 발행되면 여기에 표시됩니다.' : 'Scores will appear here once reports are published.'}
          </p>
        </div>
      )}

      {/* Newsletter CTA */}
      <div className="mt-16 p-8 rounded-2xl bg-gradient-to-r from-indigo-500/5 to-purple-500/5 border border-indigo-500/15 text-center">
        <h3 className="text-xl font-bold mb-2">
          {isKo ? '점수 변동 알림 받기' : 'Get Score Update Alerts'}
        </h3>
        <p className="text-gray-400 text-sm mb-4">
          {isKo
            ? '프로젝트 점수가 변동될 때 알림을 받아보세요'
            : 'Be the first to know when project scores change'}
        </p>
        <SubscribeForm
          locale={locale}
          source="newsletter"
          translations={{
            placeholder: t('subscribe.emailPlaceholder'),
            cta: t('subscribe.cta'),
            success: t('subscribe.checkEmail'),
          }}
        />
      </div>

      {/* Stats */}
      <div className="mt-10 pt-6 border-t border-white/5 flex justify-center gap-8 text-sm text-gray-600">
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{rows.length}</div>
          <div>{isKo ? '프로젝트' : 'Projects'}</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white">7</div>
          <div>{isKo ? '평가 축' : 'Axes'}</div>
        </div>
      </div>
    </div>
  )
}
