'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Maximize2, Minimize2 } from 'lucide-react'

import { LoadingSkeleton } from './LoadingSkeleton'

interface SlideViewerProps {
  htmlUrl: string
  title: string
  projectName: string
  className?: string
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
  const [fetchError, setFetchError] = useState(false)

  // Supabase Storage public endpoint forces Content-Type: text/plain regardless
  // of object metadata (BCE-1696), so we fetch the HTML ourselves and rebuild a
  // blob URL with the correct mime so the iframe renders it as a document.
  useEffect(() => {
    if (!htmlUrl) {
      setBlobUrl(null)
      setFetchError(false)
      return
    }

    let cancelled = false
    let createdUrl: string | null = null
    setIsLoaded(false)
    setFetchError(false)
    setBlobUrl(null)

    ;(async () => {
      try {
        const res = await fetch(htmlUrl)
        if (!res.ok) {
          throw new Error(`fetch failed: ${res.status}`)
        }
        const buf = await res.arrayBuffer()
        if (cancelled) return
        const blob = new Blob([buf], { type: 'text/html;charset=utf-8' })
        createdUrl = URL.createObjectURL(blob)
        setBlobUrl(createdUrl)
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

        {blobUrl && !fetchError && (
          <iframe
            src={blobUrl}
            title={title}
            loading="lazy"
            referrerPolicy="no-referrer"
            sandbox="allow-scripts"
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
