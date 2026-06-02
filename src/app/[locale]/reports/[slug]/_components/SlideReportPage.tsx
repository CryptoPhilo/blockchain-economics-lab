import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getTranslations } from 'next-intl/server'

import SlideViewer from '@/components/SlideViewer'
import { getLocalizedMarketingContent } from '@/lib/report-marketing-content'
import { cleanCardSummary } from '@/lib/report-summary'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import {
  pickRequestedOrLatestReport,
  sortReportsLatestFirst,
} from '@/lib/report-versioning'
import {
  type CardDataRecord,
  getLocaleReportState,
  getLocalizedSummary,
  getReportDisplayDate,
  resolveReportPdfUrl,
  resolveSlideUrl,
} from './slide-report-utils'

type ReportTypeKey = 'econ' | 'maturity' | 'forensic'

type ReportRecord = Record<string, unknown> & {
  id: string
  project_id: string
  report_type: ReportTypeKey
  version: number
  card_keywords?: string[] | null
  card_summary_en?: string | null
  language?: string | null
  published_at?: string | null
  updated_at?: string | null
  created_at?: string | null
  is_latest?: boolean | null
  marketing_content_by_lang?: Record<string, unknown> | null
}

const localeMap: Record<string, string> = {
  en: 'en-US', ko: 'ko-KR', ja: 'ja-JP', zh: 'zh-CN',
  fr: 'fr-FR', es: 'es-ES', de: 'de-DE',
}

const themeByType: Record<ReportTypeKey, {
  badgeBg: string
  badgeText: string
  badgeBorder: string
  border: string
  emoji: string
}> = {
  econ: {
    badgeBg: 'bg-blue-500/10',
    badgeText: 'text-blue-400',
    badgeBorder: 'border-blue-500/30',
    border: 'border-blue-500/20',
    emoji: '📊',
  },
  maturity: {
    badgeBg: 'bg-green-500/10',
    badgeText: 'text-green-400',
    badgeBorder: 'border-green-500/30',
    border: 'border-green-500/20',
    emoji: '🌱',
  },
  forensic: {
    badgeBg: 'bg-red-500/10',
    badgeText: 'text-red-400',
    badgeBorder: 'border-red-500/30',
    border: 'border-red-500/20',
    emoji: '🔍',
  },
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter(isNonEmptyString)
}

function getLocalizedKeywords(
  locale: string,
  report: ReportRecord,
  cardData: CardDataRecord | null,
): string[] {
  const keywordsByLang = cardData?.keywords_by_lang as Record<string, unknown> | undefined
  const localeKeywords = asStringArray(
    keywordsByLang?.[locale]
    ?? cardData?.[`keywords_${locale}`],
  )

  if (localeKeywords.length > 0) return localeKeywords

  if (report.language === locale) {
    const genericKeywords = asStringArray(cardData?.keywords ?? report.card_keywords)
    if (genericKeywords.length > 0) return genericKeywords
  }

  return asStringArray(
    keywordsByLang?.en
    ?? cardData?.keywords_en
    ?? (report.language === 'en' ? report.card_keywords : undefined)
    ?? (report.language === 'en' ? cardData?.keywords : undefined),
  )
}

function pickDefaultReportForLocale(
  sortedRows: ReportRecord[],
  locale: string,
): ReportRecord | undefined {
  const seenVersions = new Set<number>()

  for (const row of sortedRows) {
    const version = Number(row.version || 0)
    if (seenVersions.has(version)) continue
    seenVersions.add(version)

    const versionRows = sortedRows.filter((candidate) => Number(candidate.version || 0) === version)
    if (getLocaleReportState(versionRows, locale).status === 'available') {
      return row
    }
  }

  return sortedRows[0]
}

interface SlideReportPageProps {
  locale: string
  slug: string
  reportType: ReportTypeKey
  requestedVersion?: number | null
  requestedLanguage?: string | null
}

export async function SlideReportPage({
  locale,
  slug,
  reportType,
  requestedVersion,
  requestedLanguage,
}: SlideReportPageProps) {
  const t = await getTranslations('slideReportDetail')
  const supabase = await createServerSupabaseClient()

  const { data: project } = await supabase
    .from('tracked_projects')
    .select('*')
    .eq('slug', slug)
    .single()

  if (!project) notFound()

  const { data: allRows } = await supabase
    .from('project_reports')
    .select('*')
    .eq('project_id', project.id)
    .eq('report_type', reportType)
    .in('status', ['published', 'coming_soon', 'in_review'])
    .order('updated_at', { ascending: false })

  const sortedRows = sortReportsLatestFirst((allRows || []) as ReportRecord[])
  const requestedOrLatest = requestedVersion || requestedLanguage
    ? pickRequestedOrLatestReport(sortedRows, {
        version: requestedVersion,
        language: requestedLanguage,
      })
    : pickDefaultReportForLocale(sortedRows, locale)
  const versionRows = requestedOrLatest
    ? sortedRows.filter((row) => Number(row.version || 0) === Number(requestedOrLatest.version || 0))
    : []
  const reportState = getLocaleReportState(versionRows, locale)
  if (reportState.status === 'not_found') notFound()

  const report = reportState.status === 'available' ? reportState.report : null
  const isLocalePending = reportState.status === 'locale_pending'

  const mergedSlideUrls: Record<string, string> = {}
  for (const row of versionRows ?? []) {
    const urls = row?.slide_html_urls_by_lang as Record<string, unknown> | null | undefined
    if (urls && typeof urls === 'object') {
      for (const [k, v] of Object.entries(urls)) {
        if (typeof v === 'string' && v && !mergedSlideUrls[k]) mergedSlideUrls[k] = v
      }
    }
  }

  const theme = themeByType[reportType]
  const reportLabel =
    reportType === 'econ'
      ? t('econLabel')
      : reportType === 'maturity'
        ? t('maturityLabel')
        : t('forensicLabel')
  const reportTypeName =
    reportType === 'econ'
      ? t('econTypeName')
      : reportType === 'maturity'
        ? t('maturityTypeName')
        : t('forensicTypeName')
  const allReportsHref = reportType === 'forensic' ? `/${locale}/reports` : `/${locale}/score`

  const cardData = report?.card_data as CardDataRecord | null
  const slideUrl = report ? resolveSlideUrl(mergedSlideUrls, locale) : null
  const reportPdfUrl = report ? resolveReportPdfUrl(report, locale) : null

  const keywords = report ? getLocalizedKeywords(locale, report, cardData) : []
  const summary = report ? cleanCardSummary(getLocalizedSummary(locale, report, cardData)) : ''
  const marketingContent = report ? getLocalizedMarketingContent(report, locale, summary) : ''

  const score =
    report && reportType === 'maturity'
      ? (project.maturity_score ?? cardData?.maturity_score ?? cardData?.score ?? null)
      : report && reportType === 'forensic'
        ? (report.card_risk_score ?? cardData?.risk_score ?? cardData?.score ?? null)
      : report
        ? (cardData?.economy_score ?? cardData?.score ?? null)
        : null

  const generatedAt = getReportDisplayDate(versionRows, report)

  return (
    <div className="min-h-screen">
      {/* Hero header */}
      <div className={`relative border-b ${theme.border} bg-gradient-to-b from-gray-950 via-gray-950 to-transparent`}>
        <div className="max-w-5xl mx-auto px-6 pt-10 pb-12">
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-8">
            <Link href={`/${locale}`} className="hover:text-indigo-400 transition-colors">
              {t('home')}
            </Link>
            <span>/</span>
            <Link href={allReportsHref} className="hover:text-indigo-400 transition-colors">
              {reportLabel}
            </Link>
            <span>/</span>
            <span className="text-gray-300">{project.name}</span>
          </div>

          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-8">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <span className={`px-3 py-1 rounded-lg text-xs font-bold uppercase ${theme.badgeBg} ${theme.badgeText} border ${theme.badgeBorder}`}>
                  {theme.emoji} {reportLabel}
                </span>
                {typeof score === 'number' && (
                  <span className={`px-3 py-1 rounded-lg text-xs font-bold ${theme.badgeBg} ${theme.badgeText} border ${theme.badgeBorder}`}>
                    {t('scoreLabel')} {score}
                  </span>
                )}
              </div>

              <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
                {project.name}
                <span className="text-lg text-gray-500 font-normal ml-3">{project.symbol}</span>
              </h1>

              {summary && (
                <p className="text-gray-400 text-lg leading-relaxed max-w-2xl mt-4">
                  {summary}
                </p>
              )}
              {isLocalePending && (
                <p className="text-gray-400 text-lg leading-relaxed max-w-2xl mt-4">
                  {t('localePendingHeroDesc', { locale: locale.toUpperCase() })}
                </p>
              )}
              {marketingContent && (
                <div className="mt-6 max-w-2xl rounded-2xl border border-white/10 bg-white/[0.04] p-5">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">
                    {locale === 'ko' ? '투자 관점' : 'Investment View'}
                  </p>
                  <p className="whitespace-pre-line text-base leading-7 text-gray-300">
                    {marketingContent}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* Slide viewer or fallback */}
        <div className="mb-10">
          {slideUrl ? (
            <SlideViewer
              htmlUrl={slideUrl}
              title={`${project.name} ${reportLabel}`}
              projectName={project.name}
            />
          ) : isLocalePending ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center">
              <p className="text-base font-semibold text-white mb-2">
                {t('localePendingTitle')}
              </p>
              <p className="text-sm text-gray-400">
                {t('localePendingDesc', { locale: locale.toUpperCase() })}
              </p>
            </div>
          ) : reportPdfUrl ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center">
              <p className="text-base font-semibold text-white mb-2">
                {locale === 'ko' ? 'PDF 보고서를 열 수 있습니다' : 'PDF report is available'}
              </p>
              <p className="text-sm text-gray-400 mb-6">
                {locale === 'ko'
                  ? '슬라이드 뷰어는 아직 준비 중이지만 원문 PDF 보고서는 공개되어 있습니다.'
                  : 'The slide viewer is still being prepared, but the source PDF report is published.'}
              </p>
              <a
                href={reportPdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={`inline-flex items-center justify-center rounded-lg border px-5 py-3 text-sm font-semibold transition-colors ${theme.badgeBg} ${theme.badgeText} ${theme.badgeBorder} hover:bg-white/10`}
              >
                {locale === 'ko' ? 'PDF 보고서 열기' : 'Open PDF Report'} →
              </a>
            </div>
          ) : (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center">
              <p className="text-base font-semibold text-white mb-2">
                {t('slideComingSoonTitle')}
              </p>
              <p className="text-sm text-gray-400">
                {t('slideComingSoonDesc')}
              </p>
            </div>
          )}
        </div>

        {slideUrl && reportPdfUrl && (
          <div className="mb-10 rounded-xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-white">
                  {locale === 'ko' ? '원문 PDF' : 'Source PDF'}
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  {locale === 'ko'
                    ? '슬라이드와 함께 PDF 보고서도 열람할 수 있습니다.'
                    : 'The PDF report is available alongside the slide viewer.'}
                </p>
              </div>
              <a
                href={reportPdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={`inline-flex shrink-0 items-center justify-center rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ${theme.badgeBg} ${theme.badgeText} ${theme.badgeBorder} hover:bg-white/10`}
              >
                {locale === 'ko' ? 'PDF 열기' : 'Open PDF'} →
              </a>
            </div>
          </div>
        )}

        {/* Keywords */}
        {keywords.length > 0 && (
          <div className="mb-10">
            <h2 className="text-xl font-bold text-white mb-4">{t('keyFindings')}</h2>
            <div className="flex flex-wrap gap-3">
              {keywords.map((kw, i) => (
                <span
                  key={`${kw}-${i}`}
                  className={`px-4 py-2 rounded-xl text-sm font-semibold ${theme.badgeBg} ${theme.badgeText} border ${theme.badgeBorder}`}
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Metadata grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{t('reportType')}</p>
            <p className="text-white font-semibold">{reportTypeName}</p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{t('versionLabel')}</p>
            <p className="text-white font-semibold">{report ? `v${report.version || 1}` : '—'}</p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{t('analysisDate')}</p>
            <p className="text-white font-semibold">
              {generatedAt
                ? new Date(generatedAt).toLocaleDateString(localeMap[locale] || 'en-US', {
                    year: 'numeric', month: 'long', day: 'numeric',
                  })
                : '—'}
            </p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{t('languageLabel')}</p>
            <p className="text-white font-semibold uppercase">{locale}</p>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="rounded-xl bg-yellow-500/5 border border-yellow-500/20 p-6">
          <p className="text-xs text-yellow-600/80 leading-relaxed">
            {t('disclaimer')}
          </p>
        </div>

        {/* Back link */}
        <div className="flex justify-center mt-10">
          <Link
            href={allReportsHref}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all font-medium"
          >
            <span>←</span>
            <span>{t('backToReports')}</span>
          </Link>
        </div>
      </div>
    </div>
  )
}

export default SlideReportPage
