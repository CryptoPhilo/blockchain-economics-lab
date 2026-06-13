'use client'

import { useEffect, useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { ChevronLeft, ChevronRight } from 'lucide-react'

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

const reportTypeLabels: Record<ReportType, { en: string; ko: string; tone: string }> = {
  econ: {
    en: 'ECON',
    ko: 'ECON',
    tone: 'border-blue-400/30 bg-blue-400/10 text-blue-100',
  },
  maturity: {
    en: 'MAT',
    ko: 'MAT',
    tone: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100',
  },
  forensic: {
    en: 'FOR',
    ko: 'FOR',
    tone: 'border-red-400/30 bg-red-400/10 text-red-100',
  },
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
  const activeItem = visibleItems[normalizedActiveIndex]

  if (!activeItem) return null

  const activeLabel = reportTypeLabels[activeItem.reportType] ?? reportTypeLabels.forensic
  const canNavigate = visibleItems.length > 1

  function goToPrevious() {
    setActiveIndex((current) => (current === 0 ? visibleItems.length - 1 : current - 1))
  }

  function goToNext() {
    setActiveIndex((current) => (current + 1) % visibleItems.length)
  }

  return (
    <div className="mx-auto max-w-[1600px] px-4 sm:px-6">
      <section className="relative min-h-[600px] overflow-hidden rounded-xl border border-white/10 bg-slate-950 shadow-2xl shadow-black/40 md:min-h-[700px] xl:min-h-[760px]">
        <Image
          key={activeItem.id}
          src={activeItem.coverImageUrl}
          alt={activeItem.title}
          fill
          sizes="(min-width: 1600px) 1530px, 94vw"
          className="object-cover object-center"
          priority={normalizedActiveIndex === 0}
        />
        <div className="absolute inset-0 bg-black/25" />
        <div className="absolute inset-0 bg-gradient-to-r from-black via-black/65 to-black/5" />
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/25 to-black/15" />

        <div className="absolute inset-0 px-8 py-10 sm:px-14 md:px-20 md:py-20">
          <div className="max-w-4xl">
            <p className="text-sm font-bold tracking-normal text-white/90 md:text-base">
              {isKo ? '새로 발행된 보고서' : 'Newly published report'}
            </p>
            <h2 className="mt-7 max-w-4xl break-keep text-5xl font-black leading-[1.04] tracking-normal text-white md:text-7xl xl:text-8xl">
              {isKo ? '최신 ECON, MAT, FOR 리포트' : 'Latest ECON, MAT, FOR reports'}
            </h2>
          </div>

          <div className="absolute bottom-10 left-8 w-[calc(100%-4rem)] max-w-[620px] sm:left-14 sm:w-[620px] md:bottom-16 md:left-20">
            <div className="rounded-xl border border-white/10 bg-black/45 p-5 text-left shadow-2xl shadow-black/40 backdrop-blur-[2px] md:p-6">
              <div className={`mb-5 inline-flex w-fit items-center rounded-full border px-4 py-1.5 text-sm font-bold ${activeLabel.tone}`}>
                {isKo ? activeLabel.ko : activeLabel.en}
              </div>
              <Link href={activeItem.href} className="group block">
                <h3 className="text-3xl font-black leading-tight text-white transition-colors group-hover:text-indigo-200 md:text-4xl">
                  {activeItem.title}
                </h3>
              </Link>
              {activeItem.projectName && (
                <p className="mt-4 text-base font-bold text-gray-300">
                  {activeItem.projectName} {activeItem.projectSymbol ? `(${activeItem.projectSymbol})` : ''}
                </p>
              )}
              {activeItem.summary && (
                <p className="mt-4 line-clamp-3 text-sm leading-6 text-gray-300 md:text-base">
                  {activeItem.summary}
                </p>
              )}
              <div className="mt-6 flex flex-wrap items-center gap-3 text-base font-medium text-gray-400">
                {activeItem.publishedDate && <span>{activeItem.publishedDate}</span>}
                {activeItem.publishedDate && <span className="text-gray-700">/</span>}
                <Link href={activeItem.href} className="text-gray-200 transition-colors hover:text-white">
                  {isKo ? '리포트 보기' : 'Open report'} →
                </Link>
              </div>
            </div>
          </div>
        </div>

        {canNavigate && (
          <>
            <button
              type="button"
              onClick={goToPrevious}
              className="absolute left-5 top-[62%] z-10 inline-flex h-14 w-14 -translate-y-1/2 items-center justify-center rounded-full border border-white/25 bg-black/45 text-white shadow-lg shadow-black/40 transition-colors hover:border-white/70 hover:bg-black/70 focus:outline-none focus:ring-2 focus:ring-blue-400 md:left-6"
              aria-label={isKo ? '이전 리포트' : 'Previous report'}
            >
              <ChevronLeft aria-hidden="true" size={26} />
            </button>
            <div className="absolute bottom-5 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2" aria-label={isKo ? '리포트 선택' : 'Select report'}>
              {visibleItems.map((item, index) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveIndex(index)}
                  className={`h-2.5 rounded-full transition-all ${
                    index === normalizedActiveIndex ? 'w-8 bg-white' : 'w-2.5 bg-white/35 hover:bg-white/65'
                  }`}
                  aria-label={isKo ? `${index + 1}번째 리포트 보기` : `Show report ${index + 1}`}
                  aria-current={index === normalizedActiveIndex ? 'true' : undefined}
                />
              ))}
            </div>
            <button
              type="button"
              onClick={goToNext}
              className="absolute right-5 top-[62%] z-10 inline-flex h-14 w-14 -translate-y-1/2 items-center justify-center rounded-full border border-white/25 bg-black/45 text-white shadow-lg shadow-black/40 transition-colors hover:border-white/70 hover:bg-black/70 focus:outline-none focus:ring-2 focus:ring-blue-400 md:right-6"
              aria-label={isKo ? '다음 리포트' : 'Next report'}
            >
              <ChevronRight aria-hidden="true" size={26} />
            </button>
          </>
        )}
      </section>
    </div>
  )
}
