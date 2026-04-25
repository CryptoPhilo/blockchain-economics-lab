import Link from 'next/link'
import {
  getLocalizedTitle,
  formatRelativeTime,
  getAvailableLanguages,
  getReportFileUrl,
  LANGUAGE_NAMES,
  formatDate,
  isWithinHours
} from '@/lib/transformers'
import type { SupportedLanguage, ProjectReport } from '@/lib/types'
import { FORENSIC_LIST_CONFIG } from '@/lib/constants/forensic'

interface ForensicReportCardProps {
  report: ProjectReport
  locale: SupportedLanguage
}

export default function ForensicReportCard({ report, locale }: ForensicReportCardProps) {
  const project = report.project
  const config = FORENSIC_LIST_CONFIG
  const title = getLocalizedTitle(report, locale)
  const availableLangs = getAvailableLanguages(report)
  const reportTime = report.published_at || report.created_at
  const relativeTime = reportTime && isWithinHours(reportTime, 72)
    ? formatRelativeTime(reportTime, locale)
    : null

  return (
    <div
      className="relative flex flex-col gap-4 p-6 rounded-2xl bg-gradient-to-br from-red-500/5 via-white/[0.03] to-white/[0.03] border border-red-500/20 hover:border-red-500/40 transition-all hover:shadow-lg hover:shadow-red-500/10 scroll-mt-20"
    >
      {relativeTime && (
        <div className="absolute top-4 right-4 px-2 py-1 rounded-full bg-red-500/20 text-red-400 text-xs font-semibold">
          ⚡ {relativeTime}
        </div>
      )}

      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <div className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase shrink-0 ${config.color} ring-1 ring-red-500/30`}>
          {config.icon} {config.label}
        </div>
        <div className="flex-1 min-w-0 pr-20 sm:pr-0">
          <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
          <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
            {project && (
              <Link
                href={`/${locale}/projects/${project.slug}`}
                className="hover:text-red-400 transition-colors font-medium"
              >
                {project.name} ({project.symbol})
              </Link>
            )}
            {project?.category && (
              <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-600">{project.category}</span>
            )}
            <span>v{report.version}</span>
            {report.published_at && (
              <span>{formatDate(report.published_at)}</span>
            )}
          </div>
        </div>

        {report.status === 'coming_soon' ? (
          <span className="px-4 py-2 bg-amber-500/10 text-amber-400 text-sm font-medium rounded-lg border border-amber-500/20 cursor-default shrink-0">
            🔜 Coming Soon
          </span>
        ) : project ? (
          <Link
            href={`/${locale}/reports/forensic/${project.slug}`}
            className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 hover:text-red-300 text-sm font-medium rounded-lg transition-colors shrink-0 border border-red-500/30"
          >
            {locale === 'ko' ? '보고서 상세' : 'Report Details'} →
          </Link>
        ) : null}
      </div>

      {availableLangs.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/5">
          <span className="text-xs text-gray-600 mr-1">
            {locale === 'ko' ? '언어' : 'Languages'}:
          </span>
          {availableLangs.map((lang) => {
            const url = getReportFileUrl(report, lang)
            const badge = (
              <span
                key={lang}
                className={`px-2 py-0.5 rounded text-[11px] font-medium uppercase ${
                  lang === locale
                    ? 'bg-red-500/20 text-red-400 ring-1 ring-red-500/30'
                    : 'bg-white/5 text-gray-500 hover:bg-white/10'
                }`}
              >
                {LANGUAGE_NAMES[lang] || lang}
              </span>
            )
            if (url) {
              return (
                <a key={lang} href={url} target="_blank" rel="noopener noreferrer" className="hover:opacity-80">
                  {badge}
                </a>
              )
            }
            return badge
          })}
        </div>
      )}
    </div>
  )
}
