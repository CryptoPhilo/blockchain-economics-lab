'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Maximize2, Minimize2 } from 'lucide-react'

import { LoadingSkeleton } from './LoadingSkeleton'

interface SlideViewerProps {
  htmlUrl: string
  title: string
  projectName: string
  className?: string
}

const SLIDE_DATA_URL_PATTERN = /data:image\/(?:png|jpe?g|webp);base64,[^"'`\s)]+/gi

function extractSlideImages(html: string): string[] {
  const matches = html.match(SLIDE_DATA_URL_PATTERN) ?? []
  return Array.from(new Set(matches))
}

export function SlideViewer({
  htmlUrl,
  title,
  projectName,
  className = '',
}: SlideViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [slideImages, setSlideImages] = useState<string[]>([])
  const [currentSlide, setCurrentSlide] = useState(0)
  const [fetchError, setFetchError] = useState(false)

  // Supabase Storage public endpoint forces Content-Type: text/plain regardless
  // of object metadata (BCE-1696), so we fetch the HTML ourselves and rebuild a
  // blob URL with the correct mime so the iframe renders it as a document.
  useEffect(() => {
    if (!htmlUrl) {
      setBlobUrl(null)
      setSlideImages([])
      setCurrentSlide(0)
      setFetchError(false)
      return
    }

    let cancelled = false
    let createdUrl: string | null = null
    setIsLoaded(false)
    setFetchError(false)
    setBlobUrl(null)
    setSlideImages([])
    setCurrentSlide(0)

    ;(async () => {
      try {
        const res = await fetch(htmlUrl)
        if (!res.ok) {
          throw new Error(`fetch failed: ${res.status}`)
        }
        const html = await res.text()
        if (cancelled) return
        const images = extractSlideImages(html)
        if (images.length > 0) {
          setSlideImages(images)
          setIsLoaded(true)
        } else {
          const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
          createdUrl = URL.createObjectURL(blob)
          setBlobUrl(createdUrl)
        }
      } catch (err) {
        if (cancelled) return
        console.error('[SlideViewer] failed to fetch slide HTML', err)
        setFetchError(true)
      }
    })()

    return () => {
      cancelled = true
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl)
      }
    }
  }, [htmlUrl])

  const goToSlide = useCallback((index: number) => {
    setCurrentSlide(Math.max(0, Math.min(slideImages.length - 1, index)))
  }, [slideImages.length])

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current)
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
    }
  }, [])

  const toggleFullscreen = useCallback(async () => {
    const node = containerRef.current
    if (!node) return

    try {
      if (document.fullscreenElement === node) {
        await document.exitFullscreen()
      } else {
        await node.requestFullscreen()
      }
    } catch (err) {
      console.error('[SlideViewer] fullscreen toggle failed', err)
    }
  }, [])

  const currentImage = slideImages[currentSlide]

  return (
    <div
      className={`rounded-2xl border border-white/10 bg-white/5 overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-white/10">
        <h3 className="text-sm sm:text-base font-medium text-white/90 truncate">
          {projectName}
        </h3>
      </div>

      {/* 16:9 stage */}
      <div
        ref={containerRef}
        className="relative w-full aspect-[16/9] bg-black"
      >
        {!isLoaded && !fetchError && (
          <div className="absolute inset-0">
            <LoadingSkeleton
              variant="custom"
              className="w-full h-full aspect-[16/9]"
            />
          </div>
        )}

        {fetchError && (
          <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
            <p className="text-sm text-white/70">
              슬라이드를 불러오지 못했습니다.
            </p>
          </div>
        )}

        {currentImage && !fetchError && (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={currentImage}
              alt={`${title} slide ${currentSlide + 1}`}
              className="absolute inset-0 w-full h-full object-contain"
              draggable={false}
            />

            {slideImages.length > 1 && (
              <>
                <button
                  type="button"
                  onClick={() => goToSlide(currentSlide - 1)}
                  disabled={currentSlide === 0}
                  aria-label="이전 슬라이드"
                  className="absolute left-2 top-1/2 z-10 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-lg border border-white/10 bg-black/60 text-white/90 backdrop-blur-sm transition-colors hover:bg-black/80 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ChevronLeft className="h-5 w-5" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={() => goToSlide(currentSlide + 1)}
                  disabled={currentSlide === slideImages.length - 1}
                  aria-label="다음 슬라이드"
                  className="absolute right-2 top-1/2 z-10 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-lg border border-white/10 bg-black/60 text-white/90 backdrop-blur-sm transition-colors hover:bg-black/80 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ChevronRight className="h-5 w-5" aria-hidden="true" />
                </button>
                <div className="absolute bottom-2 left-1/2 z-10 -translate-x-1/2 rounded-full border border-white/10 bg-black/65 px-3 py-1 text-xs font-medium text-white/90 backdrop-blur-sm">
                  {currentSlide + 1} / {slideImages.length}
                </div>
              </>
            )}
          </>
        )}

        {!currentImage && blobUrl && !fetchError && (
          <iframe
            src={blobUrl}
            title={title}
            referrerPolicy="no-referrer"
            sandbox="allow-scripts"
            allow="fullscreen"
            allowFullScreen
            onLoad={() => setIsLoaded(true)}
            className="absolute inset-0 w-full h-full border-0"
          />
        )}

        {/* Fullscreen toggle */}
        <button
          type="button"
          onClick={toggleFullscreen}
          aria-label={isFullscreen ? '풀스크린 종료' : '풀스크린 전환'}
          aria-pressed={isFullscreen}
          className="absolute top-2 right-2 z-10 inline-flex items-center justify-center w-10 h-10 min-w-[40px] min-h-[40px] rounded-lg bg-black/60 hover:bg-black/80 border border-white/10 text-white/90 transition-colors backdrop-blur-sm"
        >
          {isFullscreen ? (
            <Minimize2 className="w-4 h-4" aria-hidden="true" />
          ) : (
            <Maximize2 className="w-4 h-4" aria-hidden="true" />
          )}
        </button>
      </div>
    </div>
  )
}

export default SlideViewer
