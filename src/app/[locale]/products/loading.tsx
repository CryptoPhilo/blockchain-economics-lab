import { CardSkeleton } from '@/components/LoadingSkeleton'

export default function ProductsLoading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-8">
        {/* Header Skeleton */}
        <div className="space-y-3">
          <div className="h-12 w-64 bg-white/10 rounded-lg" />
          <div className="h-6 w-96 bg-white/5 rounded-lg" />
        </div>

        {/* Filter Skeleton */}
        <div className="flex gap-3 flex-wrap">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="h-10 w-28 bg-white/5 border border-white/5 rounded-lg" />
          ))}
        </div>

        {/* Products Grid Skeleton */}
        <CardSkeleton count={6} />
      </div>
    </div>
  )
}
