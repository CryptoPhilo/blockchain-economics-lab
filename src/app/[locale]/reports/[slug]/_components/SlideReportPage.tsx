import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getTranslations } from 'next-intl/server'

import SlideViewer from '@/components/SlideViewer'
import { getLocalizedMarketingContent } from '@/lib/report-marketing-content'
import { getMatchingProjectReportAliasIds, type ProjectReportAvailabilityCandidate } from '@/lib/report-availability'
import { cleanCardSummary } from '@/lib/report-summary'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import {
  sortReportsLatestFirst,
} from '@/lib/report-versioning'
import {
  type CardDataRecord,
  getLocaleReportState,
  getLocalizedSummary,
  getReportDisplayDate,
  resolveSlideUrl,
} from './slide-report-utils'

type ReportTypeKey = 'econ' | 'maturity'

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
  const effectiveLocale = requestedLanguage === locale ? requestedLanguage : locale

  const { data: project } = await supabase
    .from('tracked_projects')
    .select('*')
    .eq('slug', slug)
    .single()

  if (!project) notFound()

  const { data: aliasCandidatesRaw } = await supabase
    .from('tracked_projects')
    .select('id, name, slug, symbol, coingecko_id, cmc_id, aliases')
    .in('status', ['active', 'monitoring_only'])

  const reportProjectIds = getMatchingProjectReportAliasIds(
    project as ProjectReportAvailabilityCandidate,
    (aliasCandidatesRaw || []) as ProjectReportAvailabilityCandidate[],
  )

  const { data: allRows } = await supabase
    .from('project_reports')
    .select('*')
    .in('project_id', reportProjectIds.length > 0 ? reportProjectIds : [project.id])
    .eq('report_type', reportType)
    .in('status', ['published', 'coming_soon', 'in_review'])
    .order('updated_at', { ascending: false })

  const sortedRows = sortReportsLatestFirst((allRows || []) as ReportRecord[])
  const versionRows = pickVersionRowsForLocale(sortedRows, effectiveLocale, requestedVersion)
  const reportState = getLocaleReportState(versionRows, effectiveLocale)
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
  const reportLabel = reportType === 'econ' ? t('econLabel') : t('maturityLabel')
  const reportTypeName = reportType === 'econ' ? t('econTypeName') : t('maturityTypeName')
  const allReportsHref = `/${locale}/score`

  const cardData = report?.card_data as CardDataRecord | null
  const slideUrl = report ? resolveSlideUrl(mergedSlideUrls, effectiveLocale) : null

  const keywords = report ? getLocalizedKeywords(effectiveLocale, report, cardData) : []
  const summary = report ? cleanCardSummary(getLocalizedSummary(effectiveLocale, report, cardData)) : ''
  const marketingContent = report ? getLocalizedMarketingContent(report, effectiveLocale, summary) : ''

  const score =
    report && reportType === 'maturity'
      ? (project.maturity_score ?? cardData?.maturity_score ?? cardData?.score ?? null)
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

function pickVersionRowsForLocale<T extends {
  version?: number | null
  language?: string | null
  gdrive_urls_by_lang?: Record<string, unknown> | null
  file_urls_by_lang?: Record<string, unknown> | null
  slide_html_urls_by_lang?: Record<string, unknown> | null
}>(
  rows: T[],
  locale: string,
  requestedVersion?: number | null,
): T[] {
  if (rows.length === 0) return []

  const localeRows = rows.filter((row) => (
    getLocaleReportState([row], locale).status === 'available'
  ))
  if (localeRows.length === 0) return []

  const rowsByVersion = new Map<number, T[]>()
  for (const row of localeRows) {
    const version = row.version || 0
    const list = rowsByVersion.get(version) || []
    list.push(row)
    rowsByVersion.set(version, list)
  }

  const versions = [...rowsByVersion.keys()].sort((a, b) => b - a)

  if (requestedVersion != null) {
    const exact = rowsByVersion.get(requestedVersion)
    if (exact) return exact
  }

  for (const version of versions) {
    const candidate = rowsByVersion.get(version)
    if (!candidate) continue
    if (resolveSlideUrl(mergeSlideUrls(candidate), locale)) {
      return candidate
    }
  }

  for (const version of versions) {
    const candidate = rowsByVersion.get(version)
    if (!candidate) continue
    if (getLocaleReportState(candidate, locale).status === 'available') {
      return candidate
    }
  }

  return rowsByVersion.get(versions[0]) || []
}

function mergeSlideUrls<T extends {
  slide_html_urls_by_lang?: Record<string, unknown> | null
}>(rows: T[]): Record<string, string> {
  const merged: Record<string, string> = {}
  for (const row of rows) {
    const urls = row.slide_html_urls_by_lang
    if (!urls || typeof urls !== 'object') continue
    for (const [locale, url] of Object.entries(urls)) {
      if (typeof url === 'string' && url && !merged[locale]) {
        merged[locale] = url
      }
    }
  }
  return merged
}

export default SlideReportPage
