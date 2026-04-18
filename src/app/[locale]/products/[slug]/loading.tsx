import LoadingSkeleton from '@/components/LoadingSkeleton'

export default function ProductDetailLoading() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-8">
        {/* Breadcrumb Skeleton */}
        <div className="flex gap-2 items-center">
          <div className="h-4 w-16 bg-white/5 rounded" />
          <div className="h-4 w-4 bg-white/5 rounded" />
          <div className="h-4 w-24 bg-white/5 rounded" />
          <div className="h-4 w-4 bg-white/5 rounded" />
          <div className="h-4 w-32 bg-white/5 rounded" />
        </div>

        {/* Header Skeleton */}
        <div className="space-y-4">
          <div className="flex gap-3">
            <div className="h-8 w-24 bg-indigo-500/10 border border-indigo-500/20 rounded-lg" />
            <div className="h-8 w-20 bg-white/5 border border-white/5 rounded-lg" />
          </div>
          <div className="h-14 w-3/4 bg-white/10 rounded-lg" />
          <div className="h-6 w-full bg-white/5 rounded-lg" />
          <div className="h-6 w-5/6 bg-white/5 rounded-lg" />
        </div>

        {/* Pricing Card Skeleton */}
        <div className="p-8 rounded-2xl bg-gradient-to-r from-indigo-500/5 to-purple-500/5 border border-indigo-500/10 space-y-6">
          <div className="flex justify-between items-center">
            <div className="h-10 w-32 bg-white/10 rounded-lg" />
            <div className="h-6 w-24 bg-white/5 rounded-lg" />
          </div>
          <div className="flex gap-3">
            <div className="h-12 w-32 bg-indigo-500/20 rounded-lg" />
            <div className="h-12 flex-1 bg-white/5 rounded-lg" />
          </div>
        </div>

        {/* Content Sections Skeleton */}
        <div className="space-y-6">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="space-y-3">
              <div className="h-8 w-48 bg-white/10 rounded-lg" />
              <div className="h-5 w-full bg-white/5 rounded-lg" />
              <div className="h-5 w-full bg-white/5 rounded-lg" />
              <div className="h-5 w-4/5 bg-white/5 rounded-lg" />
            </div>
          ))}
        </div>

        {/* Features List Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="flex gap-3 p-4 rounded-xl bg-white/5 border border-white/5">
              <LoadingSkeleton className="h-6 w-6 rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-5 w-3/4 bg-white/5 rounded" />
                <div className="h-4 w-full bg-white/5 rounded" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
