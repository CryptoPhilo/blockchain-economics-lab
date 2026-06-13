import Link from 'next/link'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import DisclaimerBanner from '@/components/DisclaimerBanner'
import LatestReportShowcase from '@/components/LatestReportShowcase'
import {
  getShowcasePreview,
  selectLatestReportShowcaseCandidates,
  type ReportWithCover,
} from '@/lib/latest-report-showcase'

async function hasReachableShowcaseImage(report: ReportWithCover, locale: string) {
  const preview = getShowcasePreview(report, locale)
  if (!preview.url || preview.kind !== 'image') return false

  try {
    const response = await fetch(preview.url, {
      method: 'HEAD',
      next: { revalidate: 300 },
    })
    return response.ok && response.headers.get('content-type')?.startsWith('image/')
  } catch {
    return false
  }
}

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const isKo = locale === 'ko'

  let latestReportCovers: ReportWithCover[] = []

  try {
    const supabase = await createServerSupabaseClient()
    const [latestCoverRes] = await Promise.all([
      supabase
        .from('project_reports')
        .select(`
          *,
          tracked_projects!inner(id, name, slug, symbol, chain, category),
          product:products(id, slug, title_en, title_ko, title_fr, title_es, title_de, title_ja, title_zh, cover_image_url, published_at)
        `)
        .in('report_type', ['econ', 'maturity', 'forensic'])
        .eq('status', 'published')
        .order('published_at', { ascending: false, nullsFirst: false })
        .limit(200),
    ])
    const reports = (latestCoverRes.data || []) as ReportWithCover[]
    const showcaseCandidates = selectLatestReportShowcaseCandidates(reports, locale, 40)
    const verifiedCandidates: ReportWithCover[] = []

    for (const report of showcaseCandidates) {
      if (await hasReachableShowcaseImage(report, locale)) {
        verifiedCandidates.push(report)
      }

      if (verifiedCandidates.length >= 6) break
    }

    latestReportCovers = verifiedCandidates
  } catch (e) {
    console.error('Failed to fetch data:', e)
  }

  return (
    <div>
      {/* Latest report covers */}
      {latestReportCovers.length > 0 && (
        <LatestReportShowcase reports={latestReportCovers} locale={locale} />
      )}

      <section className="border-y border-white/10 bg-slate-950 px-4 py-10 sm:px-6 md:py-12">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(420px,1.05fr)]">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                {isKo ? '분석 커버리지' : 'Research coverage'}
              </p>
              <h2 className="mt-3 max-w-2xl text-3xl font-black leading-tight tracking-normal text-white md:text-4xl">
                {isKo
                  ? '경제 설계, 성숙도, 포렌식 리스크를 같은 데이터 표면에서 비교'
                  : 'Compare economic design, maturity, and forensic risk on one research surface'}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400">
                {isKo
                  ? '보고서 노출 기준은 슬라이드 HTML만 보지 않습니다. Google Drive/PDF 자산, 지원 언어, 발행 상태를 함께 확인해 카드와 상세 페이지를 구성합니다.'
                  : 'Report visibility is not gated by slide HTML alone. Cards and detail pages use Drive/PDF assets, locale support, and publication status together.'}
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link
                  href={`/${locale}/reports`}
                  className="rounded-md bg-white px-4 py-2 text-sm font-bold text-slate-950 transition-colors hover:bg-cyan-100"
                >
                  {isKo ? '리포트 보기' : 'View reports'}
                </Link>
                <Link
                  href={`/${locale}/score`}
                  className="rounded-md border border-white/[0.12] px-4 py-2 text-sm font-bold text-slate-200 transition-colors hover:border-cyan-300/35 hover:bg-white/[0.04]"
                >
                  {isKo ? '스코어 보드' : 'Score board'}
                </Link>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              {[
                {
                  type: 'ECON',
                  title: isKo ? '경제 설계 분석' : 'Economic design',
                  desc: isKo ? '토큰노믹스, 가치 축적, 인센티브 구조' : 'Tokenomics, value accrual, incentive structure',
                  tone: 'border-sky-300/25 bg-sky-400/10',
                },
                {
                  type: 'MAT',
                  title: isKo ? '성숙도 평가' : 'Maturity assessment',
                  desc: isKo ? '7축 BCE Score, 내러티브 건강도' : '7-axis BCE Score and narrative health',
                  tone: 'border-emerald-300/25 bg-emerald-400/10',
                },
                {
                  type: 'FOR',
                  title: isKo ? '포렌식 리스크' : 'Forensic risk',
                  desc: isKo ? '온체인 포렌식, 급변동 감시, 위협 등급' : 'On-chain forensics, rapid-change monitoring, threat levels',
                  tone: 'border-rose-300/25 bg-rose-400/10',
                },
              ].map((report) => (
                <div key={report.type} className={`rounded-md border ${report.tone} p-4`}>
                  <div className="text-[11px] font-black tracking-[0.18em] text-slate-400">{report.type}</div>
                  <h3 className="mt-4 text-lg font-black text-white">{report.title}</h3>
                  <p className="mt-3 text-xs leading-5 text-slate-400">{report.desc}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-8 grid gap-3 md:grid-cols-6">
            {[
              'Slide PDF intake',
              'Source confirmation',
              'Summary extraction',
              '7-language localization',
              'Editorial review',
              'Website publishing',
            ].map((step, index) => (
              <div key={step} className="rounded-md border border-white/10 bg-slate-900/55 p-3">
                <div className="text-[11px] font-black text-cyan-200">{String(index + 1).padStart(2, '0')}</div>
                <div className="mt-3 text-xs font-semibold leading-5 text-slate-300">{step}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="max-w-6xl mx-auto px-6 py-10">
        <DisclaimerBanner />
      </section>
    </div>
  )
}
