import { ListSkeleton } from '@/components/LoadingSkeleton'

export default function DashboardLoading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-8">
        {/* Header Skeleton */}
        <div className="space-y-3">
          <div className="h-10 w-64 bg-white/10 rounded-lg" />
          <div className="h-5 w-96 bg-white/5 rounded-lg" />
        </div>

        {/* Stats Cards Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="p-6 rounded-xl bg-gradient-to-br from-indigo-500/5 to-purple-500/5 border border-indigo-500/10 space-y-3">
              <div className="h-5 w-32 bg-white/5 rounded" />
              <div className="h-10 w-24 bg-white/10 rounded-lg" />
              <div className="h-4 w-40 bg-white/5 rounded" />
            </div>
          ))}
        </div>

        {/* Tabs Skeleton */}
        <div className="flex gap-3 border-b border-white/5 pb-3">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="h-10 w-32 bg-white/5 rounded-t-lg" />
          ))}
        </div>

        {/* Purchases/Subscriptions List Skeleton */}
        <ListSkeleton count={4} />

        {/* Beta Signals Skeleton */}
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="h-3 w-24 rounded bg-cyan-500/15" />
            <div className="h-7 w-72 rounded bg-white/10" />
            <div className="h-4 w-full max-w-2xl rounded bg-white/5" />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {Array.from({ length: 2 }, (_, i) => (
              <div key={i} className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="h-3 w-16 rounded bg-white/5" />
                    <div className="h-6 w-40 rounded bg-white/10" />
                  </div>
                  <div className="h-7 w-24 rounded-full bg-white/10" />
                </div>
                <div className="h-16 rounded-xl bg-white/5" />
                <div className="h-20 rounded-xl bg-black/20" />
              </div>
            ))}
          </div>
        </div>

        {/* Referral Section Skeleton */}
        <div className="p-8 rounded-2xl bg-gradient-to-r from-green-500/5 to-emerald-500/5 border border-green-500/10 space-y-6">
          <div className="h-8 w-48 bg-white/10 rounded-lg" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <div className="h-5 w-full bg-white/5 rounded" />
              <div className="h-12 w-full bg-white/10 rounded-lg" />
            </div>
            <div className="space-y-3">
              <div className="h-5 w-32 bg-white/5 rounded" />
              <div className="h-8 w-24 bg-green-500/20 rounded-lg" />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
