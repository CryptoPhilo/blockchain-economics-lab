'use client'

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import {
  Activity,
  ArrowUpRight,
  Database,
  FileText,
  Globe2,
  Languages,
  Radio,
  ShieldCheck,
} from 'lucide-react'

import type { ReportType } from '@/lib/types'

export interface LatestReportShowcaseItem {
  id: string
  href: string
  reportType: ReportType
  title: string
  summary: string
  projectName?: string
  projectSymbol?: string
  coverImageUrl: string
  previewKind: 'image' | 'html'
  publishedDate: string | null
  localeCount: number
  hasPdfAsset: boolean
  hasSlideAsset: boolean
}

interface LatestReportShowcaseCarouselProps {
  items: LatestReportShowcaseItem[]
  locale: string
}

const reportTypeLabels: Record<ReportType, { label: string; title: string; tone: string; bar: string }> = {
  econ: {
    label: 'ECON',
    title: 'Economic design',
    tone: 'border-sky-300/30 bg-sky-400/10 text-sky-100',
    bar: 'bg-sky-300',
  },
  maturity: {
    label: 'MAT',
    title: 'Maturity score',
    tone: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
    bar: 'bg-emerald-300',
  },
  forensic: {
    label: 'FOR',
    title: 'Forensic risk',
    tone: 'border-rose-300/30 bg-rose-400/10 text-rose-100',
    bar: 'bg-rose-300',
  },
}

function ReportTypeBadge({ type }: { type: ReportType }) {
  const label = reportTypeLabels[type] ?? reportTypeLabels.forensic
  return (
    <span className={`inline-flex items-center rounded-md border px-2.5 py-1 text-[11px] font-bold ${label.tone}`}>
      {label.label}
    </span>
  )
}

function AssetBadge({ active, children }: { active: boolean; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-1 text-[11px] font-semibold ${
      active
        ? 'border-white/[0.14] bg-white/[0.06] text-slate-200'
        : 'border-white/[0.08] bg-white/[0.02] text-slate-500'
    }`}
    >
      {children}
    </span>
  )
}

function MetricTile({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string
  icon: typeof Activity
}) {
  return (
    <div className="min-w-0 border-l border-white/10 px-4 first:border-l-0">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
        <Icon size={13} aria-hidden="true" />
        <span>{label}</span>
      </div>
      <div className="mt-2 break-keep text-sm font-semibold leading-tight text-white">{value}</div>
    </div>
  )
}

function CoverPreview({ item, priority }: { item: LatestReportShowcaseItem; priority?: boolean }) {
  if (item.previewKind === 'image' && item.coverImageUrl) {
    return (
      <Image
        src={item.coverImageUrl}
        alt={item.title}
        fill
        sizes="(min-width: 1280px) 720px, 92vw"
        className="object-cover object-center"
        priority={priority}
      />
    )
  }

  return (
    <div className="absolute inset-0 bg-[linear-gradient(135deg,#020617,#0f172a_48%,#111827)]">
      <div className="absolute inset-x-8 top-10 h-px bg-cyan-300/40" />
      <div className="absolute left-8 top-16 grid w-48 gap-2">
        <span className="h-2 rounded bg-white/20" />
        <span className="h-2 w-4/5 rounded bg-white/12" />
        <span className="h-2 w-2/3 rounded bg-white/10" />
      </div>
      <div className="absolute bottom-10 right-8 h-28 w-28 rounded-full border border-cyan-300/25" />
    </div>
  )
}

export default function LatestReportShowcaseCarousel({
  items,
  locale,
}: LatestReportShowcaseCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0)
  const isKo = locale === 'ko'
  const visibleItems = items.slice(0, 6)

  useEffect(() => {
    if (visibleItems.length <= 1) return undefined

    const intervalId = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % visibleItems.length)
    }, 8000)

    return () => window.clearInterval(intervalId)
  }, [visibleItems.length])

  const normalizedActiveIndex = visibleItems.length > 0 ? activeIndex % visibleItems.length : 0
  const active = visibleItems[normalizedActiveIndex] ?? visibleItems[0]
  if (!active) return null

  const activeLabel = reportTypeLabels[active.reportType] ?? reportTypeLabels.forensic
  const localeCount = Math.max(active.localeCount, 1)

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_420px]">
        <section className="overflow-hidden rounded-md border border-white/10 bg-slate-900/70 shadow-2xl shadow-black/35">
          <div className="grid min-h-[500px] lg:grid-cols-[minmax(0,0.92fr)_minmax(420px,1.08fr)]">
            <div className="relative min-h-[300px] overflow-hidden bg-slate-950 lg:min-h-full">
              <CoverPreview item={active} priority />
              <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/[0.18] to-transparent" />
              <div className="absolute left-4 top-4 flex flex-wrap gap-2">
                <ReportTypeBadge type={active.reportType} />
                <AssetBadge active={active.hasPdfAsset}>PDF</AssetBadge>
                <AssetBadge active={active.hasSlideAsset}>SLIDE</AssetBadge>
              </div>
            </div>

            <div className="flex min-w-0 flex-col justify-between p-6 md:p-8">
              <div>
                <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  <Radio size={14} aria-hidden="true" />
                  <span>{isKo ? '리서치 콘솔' : 'Research console'}</span>
                  <span className="text-slate-700">/</span>
                  <span>{activeLabel.title}</span>
                </div>

                <h1 className="mt-5 max-w-2xl text-4xl font-black leading-[1.02] tracking-normal text-white md:text-5xl">
                  {isKo ? '최신 리포트와 검증 신호를 한 화면에서' : 'Latest reports with publication signals'}
                </h1>

                <div className="mt-7 rounded-md border border-white/10 bg-slate-950/[0.72] p-5">
                  <div className={`mb-4 h-1 w-16 rounded-full ${activeLabel.bar}`} />
                  <h2 className="text-2xl font-black leading-tight text-white md:text-3xl">
                    {active.title}
                  </h2>

                  {active.projectName && (
                    <p className="mt-3 text-sm font-semibold text-slate-300">
                      {active.projectName} {active.projectSymbol ? `(${active.projectSymbol})` : ''}
                    </p>
                  )}

                  {active.summary && (
                    <p className="mt-4 line-clamp-3 text-sm leading-6 text-slate-400 md:text-[15px]">
                      {active.summary}
                    </p>
                  )}

                  <div className="mt-5 flex flex-wrap gap-2">
                    <AssetBadge active>{localeCount}/7 locales</AssetBadge>
                    <AssetBadge active={active.hasPdfAsset}>Drive/PDF asset</AssetBadge>
                    <AssetBadge active={active.hasSlideAsset}>HTML slide asset</AssetBadge>
                    <AssetBadge active>Published</AssetBadge>
                  </div>
                </div>
              </div>

              <div className="mt-7 grid grid-cols-2 gap-y-5 border-t border-white/10 pt-5 md:grid-cols-4">
                <MetricTile label="Type" value={activeLabel.label} icon={FileText} />
                <MetricTile label="Locales" value={`${localeCount}/7`} icon={Languages} />
                <MetricTile label="Source" value={active.hasPdfAsset ? 'PDF ready' : 'Pending'} icon={Database} />
                <MetricTile label="Date" value={active.publishedDate ?? 'Latest'} icon={Activity} />
              </div>

              <Link
                href={active.href}
                className="mt-7 inline-flex w-fit items-center gap-2 rounded-md bg-white px-4 py-2 text-sm font-bold text-slate-950 transition-colors hover:bg-cyan-100"
              >
                {isKo ? '리포트 열기' : 'Open report'}
                <ArrowUpRight size={16} aria-hidden="true" />
              </Link>
            </div>
          </div>
        </section>

        <aside className="rounded-md border border-white/10 bg-slate-900/70 p-5 shadow-2xl shadow-black/25">
          <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {isKo ? '운영 계약' : 'Operating contract'}
              </p>
              <h2 className="mt-2 text-xl font-black text-white">ECON / MAT / FOR</h2>
            </div>
            <ShieldCheck className="text-cyan-200" size={24} aria-hidden="true" />
          </div>

          <div className="mt-5 space-y-3">
            {[
              isKo ? 'Slide2 PDF intake' : 'Slide2 PDF intake',
              isKo ? 'Source confirmation' : 'Source confirmation',
              isKo ? 'Summary extraction' : 'Summary extraction',
              isKo ? '7-language localization' : '7-language localization',
              isKo ? 'Editorial review' : 'Editorial review',
              isKo ? 'Website publishing' : 'Website publishing',
            ].map((step, index) => (
              <div key={step} className="flex items-center gap-3 rounded-md border border-white/[0.07] bg-slate-950/55 px-3 py-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded bg-white/[0.06] text-[11px] font-bold text-slate-300">
                  {index + 1}
                </span>
                <span className="text-sm font-medium text-slate-300">{step}</span>
              </div>
            ))}
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <div className="rounded-md border border-white/[0.07] bg-slate-950/55 p-3">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                <Globe2 size={13} aria-hidden="true" />
                Locales
              </div>
              <div className="mt-2 text-lg font-black text-white">7</div>
            </div>
            <div className="rounded-md border border-white/[0.07] bg-slate-950/55 p-3">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                <Activity size={13} aria-hidden="true" />
                Remote
              </div>
              <div className="mt-2 text-lg font-black text-white">GitHub Actions</div>
            </div>
          </div>
        </aside>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {visibleItems.map((item, index) => {
          const label = reportTypeLabels[item.reportType] ?? reportTypeLabels.forensic
          const selected = index === normalizedActiveIndex

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveIndex(index)}
              className={`min-w-0 rounded-md border p-4 text-left transition-colors ${
                selected
                  ? 'border-cyan-300/35 bg-cyan-300/10'
                  : 'border-white/10 bg-slate-900/70 hover:border-white/20 hover:bg-slate-900'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className={`h-1.5 w-10 rounded-full ${label.bar}`} />
                <span className="text-[11px] font-bold text-slate-500">{label.label}</span>
              </div>
              <div className="mt-3 truncate text-sm font-bold text-white">{item.title}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                <AssetBadge active={item.localeCount > 0}>{Math.max(item.localeCount, 1)}/7</AssetBadge>
                <AssetBadge active={item.hasPdfAsset}>PDF</AssetBadge>
                <AssetBadge active={item.hasSlideAsset}>SLIDE</AssetBadge>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
