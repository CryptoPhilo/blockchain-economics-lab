export default function ScoreLoading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-8">
        {/* Header Skeleton */}
        <div className="text-center space-y-4">
          <div className="h-12 w-96 mx-auto bg-white/10 rounded-lg" />
          <div className="h-6 w-full max-w-2xl mx-auto bg-white/5 rounded-lg" />
        </div>

        {/* Score Methodology Card Skeleton */}
        <div className="p-8 rounded-2xl bg-gradient-to-r from-indigo-500/5 to-purple-500/5 border border-indigo-500/10 space-y-4">
          <div className="h-8 w-64 bg-white/10 rounded-lg" />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="p-4 rounded-xl bg-white/5 space-y-2">
                <div className="h-6 w-16 bg-indigo-500/20 rounded-lg" />
                <div className="h-4 w-24 bg-white/5 rounded" />
                <div className="h-3 w-full bg-white/5 rounded" />
              </div>
            ))}
          </div>
        </div>

        {/* Search & Filter Skeleton */}
        <div className="flex gap-4 flex-col md:flex-row">
          <div className="flex-1 h-12 bg-white/5 border border-white/5 rounded-lg" />
          <div className="flex gap-3">
            {Array.from({ length: 2 }, (_, i) => (
              <div key={i} className="h-12 w-32 bg-white/5 border border-white/5 rounded-lg" />
            ))}
          </div>
        </div>

        {/* Table Header Skeleton */}
        <div className="rounded-xl bg-white/5 border border-white/5 overflow-hidden">
          <div className="grid grid-cols-5 gap-4 p-4 bg-white/5 border-b border-white/5">
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="h-5 bg-white/5 rounded" />
            ))}
          </div>

          {/* Table Rows Skeleton */}
          <div className="divide-y divide-white/5">
            {Array.from({ length: 10 }, (_, i) => (
              <div key={i} className="grid grid-cols-5 gap-4 p-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 bg-white/5 rounded-lg" />
                  <div className="space-y-2 flex-1">
                    <div className="h-4 w-24 bg-white/5 rounded" />
                    <div className="h-3 w-16 bg-white/5 rounded" />
                  </div>
                </div>
                <div className="h-4 w-20 bg-white/5 rounded" />
                <div className="h-6 w-16 bg-indigo-500/20 rounded-lg" />
                <div className="h-6 w-16 bg-green-500/20 rounded-lg" />
                <div className="h-8 w-24 bg-white/5 rounded-lg" />
              </div>
            ))}
          </div>
        </div>

        {/* Pagination Skeleton */}
        <div className="flex justify-between items-center">
          <div className="h-5 w-32 bg-white/5 rounded" />
          <div className="flex gap-2">
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="h-10 w-10 bg-white/5 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
