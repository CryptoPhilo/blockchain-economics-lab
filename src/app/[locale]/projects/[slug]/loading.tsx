import LoadingSkeleton from '@/components/LoadingSkeleton'

export default function ProjectDetailLoading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-10">
        {/* Breadcrumb Skeleton */}
        <div className="flex gap-2 items-center">
          <div className="h-4 w-16 bg-white/5 rounded" />
          <div className="h-4 w-4 bg-white/5 rounded" />
          <div className="h-4 w-24 bg-white/5 rounded" />
          <div className="h-4 w-4 bg-white/5 rounded" />
          <div className="h-4 w-32 bg-white/5 rounded" />
        </div>

        {/* Header Section Skeleton */}
        <div className="flex gap-6 items-start">
          <LoadingSkeleton className="w-20 h-20 rounded-2xl flex-shrink-0" />
          <div className="flex-1 space-y-4">
            <div className="flex gap-3 flex-wrap">
              <div className="h-6 w-20 bg-indigo-500/10 border border-indigo-500/20 rounded-lg" />
              <div className="h-6 w-16 bg-white/5 border border-white/5 rounded-lg" />
            </div>
            <div className="h-12 w-2/3 bg-white/10 rounded-lg" />
            <div className="h-5 w-full bg-white/5 rounded-lg" />
            <div className="h-5 w-4/5 bg-white/5 rounded-lg" />
          </div>
        </div>

        {/* Key Metrics Grid Skeleton */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="p-6 rounded-xl bg-white/5 border border-white/5 space-y-2">
              <div className="h-4 w-20 bg-white/5 rounded" />
              <div className="h-8 w-full bg-white/10 rounded-lg" />
              <div className="h-3 w-16 bg-white/5 rounded" />
            </div>
          ))}
        </div>

        {/* Tabs Skeleton */}
        <div className="space-y-6">
          <div className="flex gap-3 border-b border-white/5">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="h-10 w-28 bg-white/5 rounded-t-lg" />
            ))}
          </div>

          {/* Tab Content Skeleton */}
          <div className="space-y-6">
            <div className="p-8 rounded-2xl bg-white/5 border border-white/5 space-y-4">
              <div className="h-8 w-48 bg-white/10 rounded-lg" />
              <div className="h-5 w-full bg-white/5 rounded" />
              <div className="h-5 w-full bg-white/5 rounded" />
              <div className="h-5 w-3/4 bg-white/5 rounded" />
            </div>

            {/* Chart Skeleton */}
            <div className="p-6 rounded-xl bg-white/5 border border-white/5">
              <div className="h-64 w-full bg-white/5 rounded-lg" />
            </div>

            {/* Table Skeleton */}
            <div className="space-y-3">
              {Array.from({ length: 5 }, (_, i) => (
                <div key={i} className="flex gap-4 p-4 rounded-lg bg-white/5 border border-white/5">
                  <div className="h-5 w-1/4 bg-white/5 rounded" />
                  <div className="h-5 w-1/3 bg-white/5 rounded" />
                  <div className="h-5 w-1/5 bg-white/5 rounded" />
                  <div className="h-5 w-1/6 bg-white/5 rounded" />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Reports Section Skeleton */}
        <div className="space-y-6">
          <div className="h-10 w-56 bg-white/10 rounded-lg" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="p-6 rounded-xl bg-white/5 border border-white/5 space-y-4">
                <div className="h-6 w-3/4 bg-white/10 rounded" />
                <div className="h-4 w-full bg-white/5 rounded" />
                <div className="h-4 w-5/6 bg-white/5 rounded" />
                <div className="h-10 w-full bg-indigo-500/20 rounded-lg" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
