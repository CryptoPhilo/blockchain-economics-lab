'use client'

import { useState } from 'react'

import { SlideViewer } from '@/components/SlideViewer'

const DEFAULT_URL =
  'https://example.com/humanity_protocol_slide_viewer_ko.html'

export default function SlideViewerDevPage() {
  const [url, setUrl] = useState(DEFAULT_URL)
  const [draft, setDraft] = useState(DEFAULT_URL)
  const [projectName, setProjectName] = useState('Humanity Protocol (PoC)')

  return (
    <main className="min-h-screen bg-black text-white p-4 sm:p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="space-y-2">
          <h1 className="text-xl sm:text-2xl font-semibold">
            SlideViewer Dev Sandbox (BCE-1083)
          </h1>
          <p className="text-sm text-white/60">
            QA 전용. Self-contained HTML 슬라이드 URL을 붙여 16:9 렌더링과
            풀스크린 토글을 검증합니다.
          </p>
        </header>

        <form
          className="flex flex-col sm:flex-row gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            setUrl(draft)
          }}
        >
          <input
            type="url"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="https://.../slide.html"
            className="flex-1 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:border-white/30"
          />
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="Project name"
            className="sm:w-64 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:border-white/30"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 border border-white/10 text-sm font-medium"
          >
            Load
          </button>
        </form>

        <SlideViewer
          htmlUrl={url}
          title={`${projectName} slide deck`}
          projectName={projectName}
        />
      </div>
    </main>
  )
}
