import LoadingSkeleton from '@/components/LoadingSkeleton'

export default function ForensicReportLoading() {
  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-10">
        {/* Breadcrumb Skeleton */}
        <div className="flex gap-2 items-center">
          <div className="h-4 w-16 bg-white/5 rounded" />
          <div className="h-4 w-4 bg-white/5 rounded" />
          <div className="h-4 w-24 bg-white/5 rounded" />
          <div className="h-4 w-4 bg-white/5 rounded" />
          <div className="h-4 w-48 bg-white/5 rounded" />
        </div>

        {/* Header Section */}
        <div className="space-y-6">
          <div className="flex gap-3 flex-wrap">
            <div className="h-7 w-32 bg-red-500/10 border border-red-500/20 rounded-lg" />
            <div className="h-7 w-24 bg-white/5 border border-white/5 rounded-lg" />
          </div>
          <div className="h-14 w-3/4 bg-white/10 rounded-lg" />
          <div className="flex gap-6 text-sm">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="flex gap-2 items-center">
                <div className="h-5 w-5 bg-white/5 rounded" />
                <div className="h-4 w-24 bg-white/5 rounded" />
              </div>
            ))}
          </div>
        </div>

        {/* Key Findings Card */}
        <div className="p-8 rounded-2xl bg-gradient-to-r from-red-500/5 to-orange-500/5 border border-red-500/10 space-y-4">
          <div className="h-8 w-48 bg-white/10 rounded-lg" />
          <div className="space-y-3">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="flex gap-3 items-start">
                <LoadingSkeleton className="h-6 w-6 rounded-full flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-5 w-full bg-white/5 rounded" />
                  <div className="h-5 w-4/5 bg-white/5 rounded" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Report Sections */}
        <div className="space-y-8">
          {Array.from({ length: 5 }, (_, sectionIdx) => (
            <div key={sectionIdx} className="space-y-4">
              <div className="h-9 w-64 bg-white/10 rounded-lg" />
              <div className="space-y-3">
                {Array.from({ length: 3 }, (_, i) => (
                  <div key={i} className="h-5 w-full bg-white/5 rounded" />
                ))}
                <div className="h-5 w-4/5 bg-white/5 rounded" />
              </div>

              {/* Chart/Table Placeholder */}
              {sectionIdx % 2 === 0 && (
                <div className="p-6 rounded-xl bg-white/5 border border-white/5">
                  <div className="h-48 w-full bg-white/5 rounded-lg" />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Risk Assessment */}
        <div className="p-8 rounded-2xl bg-gradient-to-r from-orange-500/5 to-yellow-500/5 border border-orange-500/10 space-y-6">
          <div className="h-8 w-56 bg-white/10 rounded-lg" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="p-4 rounded-xl bg-white/5 space-y-2">
                <div className="h-10 w-10 bg-orange-500/20 rounded-full" />
                <div className="h-5 w-24 bg-white/5 rounded" />
                <div className="h-8 w-16 bg-white/10 rounded-lg" />
              </div>
            ))}
          </div>
        </div>

        {/* Download/Share Actions */}
        <div className="flex gap-4 pt-6 border-t border-white/5">
          <div className="h-12 flex-1 bg-indigo-500/20 rounded-lg" />
          <div className="h-12 w-32 bg-white/5 border border-white/5 rounded-lg" />
        </div>

        {/* Related Reports */}
        <div className="space-y-6 pt-8 border-t border-white/5">
          <div className="h-8 w-48 bg-white/10 rounded-lg" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="p-6 rounded-xl bg-white/5 border border-white/5 space-y-4">
                <div className="h-6 w-3/4 bg-white/10 rounded" />
                <div className="h-4 w-full bg-white/5 rounded" />
                <div className="h-4 w-5/6 bg-white/5 rounded" />
                <div className="h-10 w-full bg-white/5 rounded-lg" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
