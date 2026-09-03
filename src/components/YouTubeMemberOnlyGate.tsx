import Link from 'next/link'
import { ExternalLink, Lock, LogIn, Video } from 'lucide-react'

const BCELAB_YOUTUBE_JOIN_URL =
  process.env.NEXT_PUBLIC_BCELAB_YOUTUBE_JOIN_URL || 'https://www.youtube.com/@BCELAB/join'

interface YouTubeMemberOnlyGateProps {
  locale: string
  projectName: string
  reportLabel: string
  isAuthenticated: boolean
}

export default function YouTubeMemberOnlyGate({
  locale,
  projectName,
  reportLabel,
  isAuthenticated,
}: YouTubeMemberOnlyGateProps) {
  const isKo = locale === 'ko'
  const primaryHref = isAuthenticated ? `/${locale}/membership` : `/${locale}/auth`

  return (
    <div
      data-testid="youtube-member-only-gate"
      className="rounded-2xl border border-red-500/25 bg-red-500/[0.06] p-8"
    >
      <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
        <div className="flex gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-red-400/30 bg-red-500/10 text-red-200">
            <Lock className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-red-200">
              {isKo ? '유튜브 유료 멤버 전용' : 'YouTube paid members only'}
            </p>
            <h2 className="mt-2 text-xl font-bold text-white">
              {projectName} {reportLabel}
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-400">
              {isKo
                ? '이 보고서 슬라이드는 BCELAB 유튜브 채널 유료 가입자에게만 제공됩니다. 유튜브에서 채널 멤버십에 가입한 뒤 이 사이트에서 멤버십 인증을 완료하면 열람할 수 있습니다.'
                : 'This report slide deck is available only to paid members of the BCELAB YouTube channel. Join the channel on YouTube, then verify your membership here to view the slides.'}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 flex-col gap-3 sm:flex-row md:flex-col">
          <a
            href={BCELAB_YOUTUBE_JOIN_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-red-500"
          >
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
            <span>{isKo ? '유튜브 유료 가입' : 'Join on YouTube'}</span>
          </a>
          <Link
            href={primaryHref}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-red-50"
          >
            {isAuthenticated ? (
              <Video className="h-4 w-4" aria-hidden="true" />
            ) : (
              <LogIn className="h-4 w-4" aria-hidden="true" />
            )}
            <span>{isAuthenticated ? (isKo ? '멤버십 인증' : 'Verify membership') : (isKo ? '로그인' : 'Sign in')}</span>
          </Link>
        </div>
      </div>
    </div>
  )
}
