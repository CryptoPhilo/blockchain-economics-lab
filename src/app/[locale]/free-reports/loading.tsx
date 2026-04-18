import { CardSkeleton } from '@/components/LoadingSkeleton'

export default function FreeReportsLoading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-8">
        {/* Header Skeleton */}
        <div className="text-center space-y-4">
          <div className="h-12 w-80 mx-auto bg-white/10 rounded-lg" />
          <div className="h-6 w-full max-w-2xl mx-auto bg-white/5 rounded-lg" />
        </div>

        {/* Lead Magnet Banner Skeleton */}
        <div className="p-8 rounded-2xl bg-gradient-to-r from-indigo-500/5 to-purple-500/5 border border-indigo-500/10 space-y-4">
          <div className="h-8 w-64 bg-white/10 rounded-lg mx-auto" />
          <div className="h-5 w-96 bg-white/5 rounded-lg mx-auto" />
          <div className="h-12 w-80 bg-white/10 rounded-lg mx-auto" />
        </div>

        {/* Reports Grid Skeleton */}
        <CardSkeleton count={6} />
      </div>
    </div>
  )
}
