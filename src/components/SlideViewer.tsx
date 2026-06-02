'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Maximize2, Minimize2 } from 'lucide-react'

import { LoadingSkeleton } from './LoadingSkeleton'

const FULLSCREEN_CHROME_VISIBLE_MS = 2400
const SLIDE_VIEWER_INTERACTION_MESSAGE = 'bcelab-slide-viewer-interaction'
const SLIDE_VIEWER_FULLSCREEN_STATE_MESSAGE = 'bcelab-slide-viewer-fullscreen-state'

interface SlideViewerProps {
  htmlUrl: string
  title: string
  projectName: string
  className?: string
}

export function enhanceSlideViewerHtmlForEmbed(html: string) {
  if (!html.includes('viewer-container') || html.includes('data-bcelab-fullscreen-overlay="true"')) {
    return html
  }

  const fullscreenOverlayCss = `
body.bcelab-parent-fullscreen {
  min-height: 100vh;
  overflow: hidden;
}

body.bcelab-parent-fullscreen .viewer-container,
.viewer-container:fullscreen,
.viewer-container:-webkit-full-screen {
  width: 100vw;
  max-width: none;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #050712;
}

body.bcelab-parent-fullscreen .slide-wrapper,
.viewer-container:fullscreen .slide-wrapper,
.viewer-container:-webkit-full-screen .slide-wrapper {
  width: 100vw;
  height: 100vh;
  padding-bottom: 0;
  border-radius: 0;
  box-shadow: none;
}

body.bcelab-parent-fullscreen .title-bar,
body.bcelab-parent-fullscreen .controls,
.viewer-container:fullscreen .title-bar,
.viewer-container:fullscreen .controls,
.viewer-container:-webkit-full-screen .title-bar,
.viewer-container:-webkit-full-screen .controls {
  position: absolute;
  left: max(12px, env(safe-area-inset-left));
  right: max(12px, env(safe-area-inset-right));
  z-index: 30;
  margin: 0;
  padding: 8px 10px;
  border: 1px solid rgba(255,255,255,0.14);
  border-radius: 12px;
  background: rgba(8,10,24,0.76);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-8px);
  transition: opacity 180ms ease, transform 180ms ease;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

body.bcelab-parent-fullscreen .title-bar,
.viewer-container:fullscreen .title-bar,
.viewer-container:-webkit-full-screen .title-bar {
  top: max(12px, env(safe-area-inset-top));
}

body.bcelab-parent-fullscreen .controls,
.viewer-container:fullscreen .controls,
.viewer-container:-webkit-full-screen .controls {
  bottom: max(12px, env(safe-area-inset-bottom));
  transform: translateY(8px);
}

body.bcelab-parent-fullscreen.bcelab-chrome-visible .title-bar,
body.bcelab-parent-fullscreen.bcelab-chrome-visible .controls,
.viewer-container.bcelab-chrome-visible:fullscreen .title-bar,
.viewer-container.bcelab-chrome-visible:fullscreen .controls,
.viewer-container.bcelab-chrome-visible:-webkit-full-screen .title-bar,
.viewer-container.bcelab-chrome-visible:-webkit-full-screen .controls {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

body.bcelab-parent-fullscreen .nav-overlay,
.viewer-container:fullscreen .nav-overlay,
.viewer-container:-webkit-full-screen .nav-overlay {
  z-index: 20;
}
`

  const fullscreenOverlayScript = `
let bcelabChromeTimer = null;

function bcelabIsViewerFullscreen() {
  const viewer = document.getElementById('viewer');
  return document.fullscreenElement === viewer || document.webkitFullscreenElement === viewer;
}

function bcelabShouldAutoHideChrome() {
  return document.body.classList.contains('bcelab-parent-fullscreen') || bcelabIsViewerFullscreen();
}

function bcelabSetChromeVisible(visible) {
  const viewer = document.getElementById('viewer');
  if (!viewer) return;
  const enabled = visible && bcelabShouldAutoHideChrome();
  viewer.classList.toggle('bcelab-chrome-visible', enabled);
  document.body.classList.toggle('bcelab-chrome-visible', enabled);
  if (bcelabChromeTimer) window.clearTimeout(bcelabChromeTimer);
  if (enabled) {
    bcelabChromeTimer = window.setTimeout(() => bcelabSetChromeVisible(false), ${FULLSCREEN_CHROME_VISIBLE_MS});
  }
}

function bcelabRevealChrome() {
  bcelabSetChromeVisible(true);
  try {
    window.parent?.postMessage({ type: '${SLIDE_VIEWER_INTERACTION_MESSAGE}' }, '*');
  } catch (_) {}
}

function bcelabInstallFullscreenOverlayControls() {
  const viewer = document.getElementById('viewer');
  if (!viewer || viewer.dataset.bcelabFullscreenOverlayInstalled === 'true') return;
  viewer.dataset.bcelabFullscreenOverlayInstalled = 'true';
  viewer.addEventListener('touchstart', bcelabRevealChrome, { passive: true });
  viewer.addEventListener('pointerdown', bcelabRevealChrome);
  viewer.addEventListener('mousemove', bcelabRevealChrome);
  document.addEventListener('fullscreenchange', () => bcelabSetChromeVisible(false));
  document.addEventListener('webkitfullscreenchange', () => bcelabSetChromeVisible(false));
  window.addEventListener('message', (event) => {
    if (event.data?.type !== '${SLIDE_VIEWER_FULLSCREEN_STATE_MESSAGE}') return;
    document.body.classList.toggle('bcelab-parent-fullscreen', Boolean(event.data.active));
    bcelabSetChromeVisible(false);
  });
}

bcelabInstallFullscreenOverlayControls();
`

  return html
    .replace('</style>', `${fullscreenOverlayCss}\n</style>`)
    .replace('<body>', '<body class="bcelab-slide-viewer-embed">')
    .replace(
      '<div class="viewer-container" id="viewer">',
      '<div class="viewer-container" id="viewer" data-bcelab-fullscreen-overlay="true">',
    )
    .replace('// Load first slide', `${fullscreenOverlayScript}\n// Load first slide`)
}

export function SlideViewer({
  htmlUrl,
  title,
  projectName,
  className = '',
}: SlideViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [isFullscreenChromeVisible, setIsFullscreenChromeVisible] = useState(false)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [fetchError, setFetchError] = useState(false)
  const fullscreenChromeTimerRef = useRef<number | null>(null)

  const hideFullscreenChrome = useCallback(() => {
    if (fullscreenChromeTimerRef.current) {
      window.clearTimeout(fullscreenChromeTimerRef.current)
      fullscreenChromeTimerRef.current = null
    }
    setIsFullscreenChromeVisible(false)
  }, [])

  const revealFullscreenChrome = useCallback(() => {
    if (!isFullscreen) return
    setIsFullscreenChromeVisible(true)
    if (fullscreenChromeTimerRef.current) {
      window.clearTimeout(fullscreenChromeTimerRef.current)
    }
    fullscreenChromeTimerRef.current = window.setTimeout(() => {
      setIsFullscreenChromeVisible(false)
      fullscreenChromeTimerRef.current = null
    }, FULLSCREEN_CHROME_VISIBLE_MS)
  }, [isFullscreen])

  const postFullscreenState = useCallback((active: boolean) => {
    iframeRef.current?.contentWindow?.postMessage(
      { type: SLIDE_VIEWER_FULLSCREEN_STATE_MESSAGE, active },
      '*',
    )
  }, [])

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
        const html = await res.text()
        if (cancelled) return
        const blob = new Blob([enhanceSlideViewerHtmlForEmbed(html)], { type: 'text/html;charset=utf-8' })
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
      const active = document.fullscreenElement === containerRef.current
      setIsFullscreen(active)
      postFullscreenState(active)
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
    }
  }, [postFullscreenState])

  useEffect(() => {
    if (!isFullscreen) {
      hideFullscreenChrome()
    }
    postFullscreenState(isFullscreen)
  }, [hideFullscreenChrome, isFullscreen, postFullscreenState])

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === SLIDE_VIEWER_INTERACTION_MESSAGE) {
        revealFullscreenChrome()
      }
    }

    window.addEventListener('message', handleMessage)
    return () => {
      window.removeEventListener('message', handleMessage)
      if (fullscreenChromeTimerRef.current) {
        window.clearTimeout(fullscreenChromeTimerRef.current)
      }
    }
  }, [revealFullscreenChrome])

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
        onMouseMove={revealFullscreenChrome}
        onPointerDown={revealFullscreenChrome}
        onTouchStart={revealFullscreenChrome}
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
            ref={iframeRef}
            src={blobUrl}
            title={title}
            loading="lazy"
            referrerPolicy="no-referrer"
            sandbox="allow-scripts"
            allow="fullscreen"
            allowFullScreen
            onLoad={() => {
              setIsLoaded(true)
              postFullscreenState(isFullscreen)
            }}
            className="absolute inset-0 w-full h-full border-0"
          />
        )}

        {/* Fullscreen toggle */}
        <button
          type="button"
          onClick={toggleFullscreen}
          aria-label={isFullscreen ? '풀스크린 종료' : '풀스크린 전환'}
          aria-pressed={isFullscreen}
          className={`absolute top-2 right-2 z-30 inline-flex items-center justify-center w-10 h-10 min-w-[40px] min-h-[40px] rounded-lg bg-black/60 hover:bg-black/80 border border-white/10 text-white/90 transition-all backdrop-blur-sm ${
            isFullscreen && !isFullscreenChromeVisible ? 'opacity-0 pointer-events-none' : 'opacity-100'
          }`}
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
