import Link from 'next/link'

interface PaginationProps {
  currentPage: number
  totalPages: number
  buildUrl: (page: number) => string
  locale: string
}

export default function Pagination({ currentPage, totalPages, buildUrl, locale }: PaginationProps) {
  if (totalPages <= 1) return null

  const prevLabel = locale === 'ko' ? '이전' : 'Prev'
  const nextLabel = locale === 'ko' ? '다음' : 'Next'

  const pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1)
    .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 2)
    .reduce<(number | string)[]>((acc, p, i, arr) => {
      if (i > 0 && p - (arr[i - 1] as number) > 1) acc.push('...')
      acc.push(p)
      return acc
    }, [])

  return (
    <nav className="flex items-center justify-center gap-2 mt-10">
      {currentPage > 1 && (
        <Link
          href={buildUrl(currentPage - 1)}
          className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 text-sm transition-colors"
        >
          ← {prevLabel}
        </Link>
      )}
      {pageNumbers.map((p, i) =>
        typeof p === 'string' ? (
          <span key={`dots-${i}`} className="px-2 text-gray-600">...</span>
        ) : (
          <Link
            key={p}
            href={buildUrl(p)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              p === currentPage
                ? 'bg-indigo-500 text-white'
                : 'bg-white/5 hover:bg-white/10 text-gray-400'
            }`}
          >
            {p}
          </Link>
        )
      )}
      {currentPage < totalPages && (
        <Link
          href={buildUrl(currentPage + 1)}
          className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 text-sm transition-colors"
        >
          {nextLabel} →
        </Link>
      )}
    </nav>
  )
}
