'use client'

import { useState } from 'react'
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
  publishedDate: string | null
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
  const activeItem = items[activeIndex]

  if (!activeItem) return null

  const activeLabel = reportTypeLabels[activeItem.reportType] ?? reportTypeLabels.forensic
  const canNavigate = items.length > 1

  function goToPrevious() {
    setActiveIndex((current) => (current === 0 ? items.length - 1 : current - 1))
  }

  function goToNext() {
    setActiveIndex((current) => (current + 1) % items.length)
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-8 px-6 lg:grid-cols-[minmax(300px,0.82fr)_minmax(0,1fr)] lg:items-center">
      <div className="relative mx-auto w-full max-w-[360px] lg:max-w-[430px]">
        <Link
          href={activeItem.href}
          className="group block rounded-lg border border-white/10 bg-white/[0.035] p-3 shadow-2xl shadow-black/30 transition-colors hover:border-white/20"
        >
          <div className="relative aspect-[4/5] overflow-hidden rounded-md bg-gray-900">
            <Image
              src={activeItem.coverImageUrl}
              alt={activeItem.title}
              fill
              sizes="(min-width: 1024px) 430px, (min-width: 768px) 360px, 88vw"
              className="object-cover transition-transform duration-500 group-hover:scale-[1.025]"
              priority={activeIndex === 0}
            />
          </div>
        </Link>
      </div>

      <div className="min-w-0 text-center lg:text-left">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">
          {isKo ? '최신 리포트' : 'Latest reports'}
        </p>
        <h2 className="mt-3 text-3xl font-bold leading-tight text-white md:text-5xl">
          {isKo ? '최신 ECON, MAT, FOR 리포트' : 'Latest ECON, MAT, and FOR reports'}
        </h2>

        <div className="mt-8 rounded-lg border border-white/10 bg-white/[0.03] p-5 text-left md:p-6">
          <div className={`mb-4 inline-flex w-fit items-center rounded-full border px-3 py-1 text-xs font-semibold ${activeLabel.tone}`}>
            {isKo ? activeLabel.ko : activeLabel.en}
          </div>
          <Link href={activeItem.href} className="group block">
            <h3 className="text-2xl font-bold leading-tight text-white transition-colors group-hover:text-indigo-200 md:text-3xl">
              {activeItem.title}
            </h3>
          </Link>
          {activeItem.projectName && (
            <p className="mt-4 text-sm font-medium text-gray-400">
              {activeItem.projectName} {activeItem.projectSymbol ? `(${activeItem.projectSymbol})` : ''}
            </p>
          )}
          {activeItem.summary && (
            <p className="mt-4 line-clamp-3 text-sm leading-6 text-gray-300 md:text-base">
              {activeItem.summary}
            </p>
          )}
          <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-gray-500">
            {activeItem.publishedDate && <span>{activeItem.publishedDate}</span>}
            {activeItem.publishedDate && <span className="text-gray-700">/</span>}
            <Link href={activeItem.href} className="font-medium text-gray-300 transition-colors hover:text-white">
              {isKo ? '리포트 보기' : 'Open report'} →
            </Link>
          </div>
        </div>

        {canNavigate && (
          <div className="mt-6 flex items-center justify-center gap-4 lg:justify-start">
            <button
              type="button"
              onClick={goToPrevious}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-gray-300 transition-colors hover:border-white/25 hover:text-white"
              aria-label={isKo ? '이전 리포트' : 'Previous report'}
            >
              <ChevronLeft aria-hidden="true" size={18} />
            </button>
            <div className="flex items-center gap-2" aria-label={isKo ? '리포트 선택' : 'Select report'}>
              {items.map((item, index) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveIndex(index)}
                  className={`h-2.5 rounded-full transition-all ${
                    index === activeIndex ? 'w-7 bg-white' : 'w-2.5 bg-white/30 hover:bg-white/60'
                  }`}
                  aria-label={isKo ? `${index + 1}번째 리포트 보기` : `Show report ${index + 1}`}
                  aria-current={index === activeIndex ? 'true' : undefined}
                />
              ))}
            </div>
            <button
              type="button"
              onClick={goToNext}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-gray-300 transition-colors hover:border-white/25 hover:text-white"
              aria-label={isKo ? '다음 리포트' : 'Next report'}
            >
              <ChevronRight aria-hidden="true" size={18} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
