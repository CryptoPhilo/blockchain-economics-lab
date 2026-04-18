import { ListSkeleton } from '@/components/LoadingSkeleton'

export default function ProjectsLoading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-8">
        {/* Header Skeleton */}
        <div className="space-y-3">
          <div className="h-12 w-80 bg-white/10 rounded-lg" />
          <div className="h-6 w-full max-w-2xl bg-white/5 rounded-lg" />
        </div>

        {/* Search & Filter Skeleton */}
        <div className="flex gap-4 flex-col md:flex-row">
          <div className="flex-1 h-12 bg-white/5 border border-white/5 rounded-lg" />
          <div className="flex gap-3">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="h-12 w-32 bg-white/5 border border-white/5 rounded-lg" />
            ))}
          </div>
        </div>

        {/* Stats Cards Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="p-6 rounded-xl bg-white/5 border border-white/5 space-y-2">
              <div className="h-8 w-20 bg-white/5 rounded" />
              <div className="h-10 w-32 bg-white/10 rounded-lg" />
              <div className="h-4 w-24 bg-white/5 rounded" />
            </div>
          ))}
        </div>

        {/* Projects List Skeleton */}
        <ListSkeleton count={6} />
      </div>
    </div>
  )
}
