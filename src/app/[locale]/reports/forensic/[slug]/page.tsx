import { createServerSupabaseClient } from '@/lib/supabase-server'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getTranslations } from 'next-intl/server'
import GatedDownloadButton from '@/components/GatedDownloadButton'
import { FORENSIC_LABELS, getLabel } from '@/lib/constants/forensic'
import { cleanCardSummary } from '@/lib/report-summary'

interface Props {
  params: Promise<{ locale: string; slug: string }>
}

const riskConfig: Record<string, { color: string; bg: string; border: string; stroke: string }> = {
  critical: { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', stroke: '#EF4444' },
  high: { color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', stroke: '#F97316' },
  elevated: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', stroke: '#EAB308' },
}

// Locale → Intl locale string for date formatting
const localeMap: Record<string, string> = {
  en: 'en-US', ko: 'ko-KR', ja: 'ja-JP', zh: 'zh-CN',
  fr: 'fr-FR', es: 'es-ES', de: 'de-DE',
}

export default async function ForensicReportPage({ params }: Props) {
  const { locale, slug } = await params
  const t = await getTranslations('forensicDetail')
  const supabase = await createServerSupabaseClient()

  // Fetch the project
  const { data: project } = await supabase
    .from('tracked_projects')
    .select('*')
    .eq('slug', slug)
    .single()

  if (!project) notFound()

  // Fetch the latest forensic report for this project
  const { data: report } = await supabase
    .from('project_reports')
    .select('*')
    .eq('project_id', project.id)
    .eq('report_type', 'forensic')
    .in('status', ['published', 'coming_soon'])
    .order('published_at', { ascending: false })
    .limit(1)
    .single()

  if (!report) notFound()

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cardData = report.card_data as Record<string, any> | null
  const pageCount = typeof report.page_count === 'number' && report.page_count > 0 ? report.page_count : null
  const isComingSoon = report.status === 'coming_soon'
  const level = (report.risk_level || cardData?.risk_level || 'elevated').toLowerCase()
  const config = riskConfig[level] || riskConfig.elevated
  const riskScore = report.card_risk_score ?? cardData?.risk_score ?? 0

  // Locale-aware keyword/summary resolution
  const keywordsByLang = cardData?.keywords_by_lang as Record<string, string[]> | undefined
  const keywordsLocaleKey = `keywords_${locale}`
  // Turbopack requires explicit grouping when ?? is mixed with ||.
  const localizedKeywords =
    keywordsByLang?.[locale] ??
    keywordsByLang?.en ??
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ((cardData as any)?.[keywordsLocaleKey] ??
      (locale === 'ko' ? (report.card_keywords ?? cardData?.keywords_ko ?? cardData?.keywords ?? []) : []))
  const keywords: string[] =
    localizedKeywords.length > 0
      ? localizedKeywords
      : (cardData?.keywords_en ?? report.card_keywords ?? [])

  const summaryByLang = cardData?.summary_by_lang as Record<string, string> | undefined
  const summary = cleanCardSummary(
    summaryByLang?.[locale]
    || summaryByLang?.en
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    || (report as any)[`card_summary_${locale}`]
    || report.card_summary_en
    || cardData?.summary_ko
    || cardData?.summary_en
    || cardData?.summary
    || getLabel(FORENSIC_LABELS.defaultSummary, locale)
    || '',
  )

  const change24h = cardData?.price_change_24h ?? cardData?.change_24h ?? 0
  const direction = cardData?.direction ?? (change24h >= 0 ? 'up' : 'down')
  const generatedAt = cardData?.generated_at || report.published_at || report.created_at

  const levelLabel =
    level === 'critical' ? t('riskCritical')
    : level === 'high' ? t('riskHigh')
    : t('riskElevated')

  // Resolve the best available PDF URL for the current locale
  const urlsByLang = report.gdrive_urls_by_lang as Record<string, unknown> | null
  const resolveUrl = (val: unknown): string | undefined => {
    if (typeof val === 'string') return val
    if (val && typeof val === 'object' && 'url' in val) return (val as { url: string }).url
    return undefined
  }
  const localizedUrl = (urlsByLang && (resolveUrl(urlsByLang[locale]) || resolveUrl(urlsByLang['en']))) || null
  const primaryUrl = report.file_url || report.gdrive_url || localizedUrl
  const hasReport = !!primaryUrl
  const canDownload = hasReport && !isComingSoon
  const previewStatusLabel =
    isComingSoon
      ? (locale === 'ko' ? '준비 중' : 'Coming soon')
      : hasReport
        ? (locale === 'ko' ? '이용 가능' : 'Available')
        : (locale === 'ko' ? '링크 준비 중' : 'Link pending')
  const previewLengthLabel =
    pageCount
      ? `${pageCount}${locale === 'ko' ? '페이지' : ' pages'}`
      : (locale === 'ko' ? '공개 범위 미표시' : 'Length not disclosed')
  const statusToneClass = isComingSoon ? 'text-amber-300' : hasReport ? 'text-green-300' : 'text-gray-300'
  const previewCtaCopy =
    isComingSoon
      ? {
          ko: '포렌식 보고서는 공개 준비가 끝나는 대로 무료 접근 경로가 연결됩니다.',
          en: 'Free access to the forensic report will be linked once publishing is complete.',
        }
      : pageCount
        ? {
            ko: `이 미리보기가 유용하셨나요? 무료 PDF 보고서(${pageCount}페이지)를 확인해 보세요.`,
            en: `Found this preview helpful? Open the free PDF report (${pageCount} pages).`,
          }
        : {
            ko: '이 미리보기가 유용하셨나요? 무료 PDF 보고서를 확인해 보세요.',
            en: 'Found this preview helpful? Open the free PDF report.',
          }
  const reportIntroCopy = isComingSoon
    ? {
        ko: '보고서가 아직 공개 대기 중입니다. 아래 요약 정보로 현재 상태를 확인할 수 있습니다.',
        en: 'The report is still awaiting publication. The summary below shows the current available context.',
      }
    : {
        ko: '데이터가 적은 리포트라도 핵심 상태를 먼저 확인할 수 있도록 요약 정보를 정리했습니다.',
        en: 'Even when the report is sparse, the preview surfaces the core state and available context first.',
      }
  const accessPanelTitle =
    locale === 'ko'
      ? (canDownload ? '무료 PDF 열기' : '무료 PDF 공개 상태')
      : (canDownload ? 'Open Free PDF' : 'Free PDF Availability')
  const accessPanelBody = locale === 'ko' ? previewCtaCopy.ko : previewCtaCopy.en
  const accessHighlights =
    locale === 'ko'
      ? [
          `현재 상태: ${previewStatusLabel}`,
          `보고서 분량: ${previewLengthLabel}`,
          isComingSoon ? '공개 전까지는 핵심 신호만 미리보기로 제공합니다.' : '언어별 PDF 링크와 요약본 접근 경로를 한곳에 모았습니다.',
        ]
      : [
          `Status: ${previewStatusLabel}`,
          `Report length: ${previewLengthLabel}`,
          isComingSoon ? 'Until publication, the preview focuses on the highest-signal findings.' : 'PDF access and alternate language links are grouped in one place.',
        ]
  const reportCoverageTitle = locale === 'ko' ? '보고서에서 확인할 수 있는 내용' : 'What this report covers'
  const reportCoverageItems =
    locale === 'ko'
      ? [
          {
            title: '온체인 리스크 신호',
            body: '지갑 흐름, 토큰 이동, 이상 징후를 위험 점수와 함께 정리합니다.',
          },
          {
            title: '거래소·유동성 맥락',
            body: '상장 거래소 흐름과 유동성 변화를 하나의 내러티브로 읽을 수 있게 묶습니다.',
          },
          {
            title: '시장 구조 해석',
            body: '가격 움직임과 파생상품 또는 수급 맥락을 연결해 핵심 해석을 제공합니다.',
          },
        ]
      : [
          {
            title: 'On-chain risk signals',
            body: 'Wallet flow, token movement, and anomaly cues are summarized with a risk score.',
          },
          {
            title: 'Exchange and liquidity context',
            body: 'Exchange flow and liquidity shifts are grouped into one readable narrative.',
          },
          {
            title: 'Market structure interpretation',
            body: 'Price action and derivatives or flow context are connected into a concise takeaway.',
          },
        ]
  const fallbackSignals =
    [
      locale === 'ko' ? `${levelLabel} 리스크` : `${levelLabel} risk`,
      change24h !== 0
        ? (locale === 'ko'
            ? `24시간 변동 ${change24h >= 0 ? '+' : ''}${Number(change24h).toFixed(1)}%`
            : `24h move ${change24h >= 0 ? '+' : ''}${Number(change24h).toFixed(1)}%`)
        : null,
      pageCount
        ? (locale === 'ko' ? `${pageCount}페이지 보고서` : `${pageCount}-page report`)
        : null,
      locale === 'ko' ? `상태 ${previewStatusLabel}` : `Status ${previewStatusLabel}`,
    ].filter((value): value is string => Boolean(value))

  return (
    <div className="min-h-screen">
      {/* Hero header */}
      <div className={`relative border-b ${config.border} bg-gradient-to-b from-gray-950 via-gray-950 to-transparent`}>
        <div className="max-w-5xl mx-auto px-6 pt-10 pb-12">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-8">
            <Link href={`/${locale}`} className="hover:text-indigo-400 transition-colors">
              {t('home')}
            </Link>
            <span>/</span>
            <Link href={`/${locale}/reports?type=forensic`} className="hover:text-indigo-400 transition-colors">
              {t('forensicReports')}
            </Link>
            <span>/</span>
            <span className="text-gray-300">{project.name}</span>
          </div>

          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-8">
            {/* Left: project info */}
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <span className={`px-3 py-1 rounded-lg text-xs font-bold uppercase ${config.bg} ${config.color} border ${config.border}`}>
                  🔍 {t('forensic')}
                </span>
                <span className={`px-3 py-1 rounded-lg text-xs font-bold uppercase ${config.bg} ${config.color} border ${config.border}`}>
                  ⚠ {levelLabel}
                </span>
              </div>

              <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
                {project.name}
                <span className="text-lg text-gray-500 font-normal ml-3">{project.symbol}</span>
              </h1>

              {change24h !== 0 && (
                <p className="text-lg mb-4">
                  <span className="text-gray-500 mr-2">{t('change24h')}:</span>
                  <span className={change24h >= 0 ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
                    {change24h >= 0 ? '+' : ''}{Number(change24h).toFixed(1)}%
                    {direction === 'up' ? ' ↑' : ' ↓'}
                  </span>
                </p>
              )}

              <p className="text-gray-400 text-lg leading-relaxed max-w-2xl">
                {summary}
              </p>
            </div>

            {/* Right: risk gauge */}
            <div className="flex flex-col items-center px-8 py-6 rounded-2xl bg-white/[0.03] border border-white/10 min-w-[200px]">
              <div className="relative w-24 h-24 mb-3">
                <svg className="w-24 h-24" viewBox="0 0 96 96">
                  <circle cx="48" cy="48" r="40" fill="none" stroke="#1F2937" strokeWidth="6" />
                  <circle
                    cx="48" cy="48" r="40" fill="none"
                    stroke={config.stroke}
                    strokeWidth="6" strokeLinecap="round"
                    strokeDasharray={`${(riskScore / 100) * 251.3} 251.3`}
                    transform="rotate(-90 48 48)"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className={`text-3xl font-black ${config.color}`}>{riskScore}</span>
                </div>
              </div>
              <p className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                {t('riskScore')}
              </p>
              <p className={`text-sm font-bold ${config.color} mt-1`}>
                {levelLabel} {t('risk')}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* Preview snapshot */}
        <div className="mb-10 rounded-[28px] border border-white/10 bg-white/[0.03] p-6 md:p-8">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.9fr)]">
            <div>
              <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between mb-5">
                <div>
                  <h2 className="text-xl font-bold text-white">
                    {locale === 'ko' ? '미리보기 요약' : 'Preview Snapshot'}
                  </h2>
                  <p className="mt-1 max-w-2xl text-sm text-gray-500">
                    {locale === 'ko' ? reportIntroCopy.ko : reportIntroCopy.en}
                  </p>
                </div>
                <p className="text-sm text-gray-400">
                  {locale === 'ko'
                    ? `현재 상태: ${previewStatusLabel}`
                    : `Current status: ${previewStatusLabel}`}
                </p>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-white/10 bg-gray-950/40 p-4">
                  <p className="mb-1 text-xs uppercase tracking-[0.2em] text-gray-500">
                    {locale === 'ko' ? '위험 점수' : 'Risk score'}
                  </p>
                  <p className={`text-lg font-bold ${config.color}`}>{riskScore}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-gray-950/40 p-4">
                  <p className="mb-1 text-xs uppercase tracking-[0.2em] text-gray-500">
                    {locale === 'ko' ? '분석 일시' : 'Analysis date'}
                  </p>
                  <p className="text-sm font-semibold text-white">
                    {generatedAt
                      ? new Date(generatedAt).toLocaleDateString(localeMap[locale] || 'en-US', {
                          year: 'numeric', month: 'short', day: 'numeric'
                        })
                      : (locale === 'ko' ? '미정' : 'Not set')}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-gray-950/40 p-4">
                  <p className="mb-1 text-xs uppercase tracking-[0.2em] text-gray-500">
                    {locale === 'ko' ? '보고서 분량' : 'Report length'}
                  </p>
                  <p className="text-sm font-semibold text-white">{previewLengthLabel}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-gray-950/40 p-4">
                  <p className="mb-1 text-xs uppercase tracking-[0.2em] text-gray-500">
                    {locale === 'ko' ? '현재 상태' : 'Current status'}
                  </p>
                  <p className={`text-sm font-semibold ${statusToneClass}`}>
                    {previewStatusLabel}
                  </p>
                </div>
              </div>
            </div>

            <aside className="rounded-[24px] border border-indigo-400/20 bg-[linear-gradient(160deg,rgba(99,102,241,0.18),rgba(17,24,39,0.92))] p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-indigo-200/80">
                {locale === 'ko' ? '리포트 액세스' : 'Report Access'}
              </p>
              <h3 className="mt-3 text-2xl font-bold text-white">
                {accessPanelTitle}
              </h3>
              <p className="mt-2 text-sm leading-6 text-indigo-100/85">
                {accessPanelBody}
              </p>

              <div className="mt-5 space-y-2">
                {accessHighlights.map((item) => (
                  <div
                    key={item}
                    className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-gray-100"
                  >
                    {item}
                  </div>
                ))}
              </div>

              <div className="mt-5 flex flex-col gap-3">
                {canDownload ? (
                  <GatedDownloadButton
                    reportId={report.id}
                    downloadUrl={primaryUrl}
                    locale={locale}
                    label={
                      pageCount
                        ? (locale === 'ko'
                            ? `무료 PDF 받기 (${pageCount}페이지)`
                            : `Get Free PDF (${pageCount} pages)`)
                        : (locale === 'ko' ? '무료 PDF 받기' : 'Get Free PDF')
                    }
                  />
                ) : (
                  <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-gray-200">
                    <p>
                      {isComingSoon
                        ? (locale === 'ko'
                            ? '무료 PDF 보고서는 아직 공개되지 않았습니다.'
                            : 'The free PDF report is not public yet.')
                        : (locale === 'ko'
                            ? '무료 PDF 링크는 아직 연결되지 않았습니다.'
                            : 'The free PDF link is not attached yet.')}
                    </p>
                    <p className="mt-2 text-gray-400">
                      {isComingSoon ? t('comingSoonDesc') : (locale === 'ko'
                        ? '출시가 완료되면 다운로드 게이트와 언어별 링크가 이 영역에 표시됩니다.'
                        : 'Once publishing completes, the download gate and language-specific links will appear here.')}
                    </p>
                  </div>
                )}

                {report.gdrive_url_free && (
                  <a
                    href={report.gdrive_url_free}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/10 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/20"
                  >
                    📄 {t('freeSummary')}
                  </a>
                )}

                {urlsByLang && Object.keys(urlsByLang).length > 1 && canDownload && (
                  <div className="flex flex-wrap gap-2">
                    <span className="mr-1 self-center text-sm text-indigo-100/75">
                      {t('otherLanguages')}
                    </span>
                    {Object.entries(urlsByLang)
                      .filter(([lang]) => lang !== locale)
                      .filter(([, val]) => resolveUrl(val))
                      .map(([lang, val]) => (
                        <a
                          key={lang}
                          href={resolveUrl(val)!}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-lg border border-white/10 bg-black/20 px-3 py-1 text-xs font-medium uppercase text-white/80 transition-colors hover:bg-black/30 hover:text-white"
                        >
                          {lang}
                        </a>
                      ))}
                  </div>
                )}
              </div>
            </aside>
          </div>
        </div>

        {/* Keywords / fallback signals */}
        {(keywords.length > 0 || fallbackSignals.length > 0) && (
          <div className="mb-10">
            <h2 className="text-xl font-bold text-white mb-4">
              {keywords.length > 0
                ? t('keyFindings')
                : (locale === 'ko' ? '핵심 신호' : 'Key Signals')}
            </h2>
            <div className="flex flex-wrap gap-3">
              {(keywords.length > 0 ? keywords : fallbackSignals).map((kw: string, i: number) => (
                <span
                  key={`${kw}-${i}`}
                  className={`px-4 py-2 rounded-xl text-sm font-semibold ${config.bg} ${config.color} border ${config.border}`}
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="mb-10 grid gap-4 md:grid-cols-3">
          {reportCoverageItems.map((item) => (
            <div key={item.title} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
              <p className="text-xs uppercase tracking-[0.22em] text-gray-500">
                {reportCoverageTitle}
              </p>
              <h3 className="mt-3 text-lg font-semibold text-white">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-gray-400">{item.body}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {t('reportType')}
            </p>
            <p className="text-white font-semibold">
              {t('reportTypeName')}
            </p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {t('versionLabel')}
            </p>
            <p className="text-white font-semibold">v{report.version || 1}</p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {t('analysisDate')}
            </p>
            <p className="text-white font-semibold">
              {generatedAt
                ? new Date(generatedAt).toLocaleDateString(localeMap[locale] || 'en-US', {
                  year: 'numeric', month: 'long', day: 'numeric'
                  })
                : '—'}
            </p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              {locale === 'ko' ? '보고서 분량' : 'Report length'}
            </p>
            <p className="text-white font-semibold">
              {pageCount
                ? `${pageCount}${locale === 'ko' ? '페이지' : ' pages'}`
                : (locale === 'ko' ? '미공개' : 'Not disclosed')}
            </p>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="rounded-xl bg-yellow-500/5 border border-yellow-500/20 p-6">
          <p className="text-xs text-yellow-600/80 leading-relaxed">
            ⚠ {t('disclaimer')}
          </p>
        </div>

        {/* Back link */}
        <div className="flex justify-center mt-10">
          <Link
            href={`/${locale}/reports?type=forensic`}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all font-medium"
          >
            <span>←</span>
            <span>{t('allForensicReports')}</span>
          </Link>
        </div>
      </div>
    </div>
  )
}
