import { CardSkeleton } from '@/components/LoadingSkeleton'

export default function ReportsLoading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-8">
        {/* Header Skeleton */}
        <div className="space-y-3">
          <div className="h-12 w-72 bg-white/10 rounded-lg" />
          <div className="h-6 w-full max-w-2xl bg-white/5 rounded-lg" />
        </div>

        {/* Filter Tabs Skeleton */}
        <div className="flex gap-3 flex-wrap border-b border-white/5 pb-3">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="h-10 w-32 bg-white/5 rounded-t-lg" />
          ))}
        </div>

        {/* Search Bar Skeleton */}
        <div className="flex gap-4">
          <div className="flex-1 h-12 bg-white/5 border border-white/5 rounded-lg" />
          <div className="h-12 w-40 bg-white/5 border border-white/5 rounded-lg" />
        </div>

        {/* Reports Grid Skeleton */}
        <CardSkeleton count={9} />
      </div>
    </div>
  )
}
