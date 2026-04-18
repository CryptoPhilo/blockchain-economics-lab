import { CardSkeleton } from '@/components/LoadingSkeleton'

export default function RootLoading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-12">
        {/* Hero Section Skeleton */}
        <section className="relative overflow-hidden bg-gradient-to-br from-gray-950 via-indigo-950 to-gray-950 py-20 px-6 rounded-2xl">
          <div className="max-w-5xl mx-auto text-center space-y-6">
            <div className="h-12 w-3/4 mx-auto bg-white/10 rounded-lg" />
            <div className="h-6 w-2/3 mx-auto bg-white/5 rounded-lg" />
            <div className="h-12 w-64 mx-auto bg-white/10 rounded-lg" />
          </div>
        </section>

        {/* Categories Skeleton */}
        <section className="space-y-6">
          <div className="h-10 w-48 bg-white/10 rounded-lg" />
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="h-32 bg-white/5 border border-white/5 rounded-xl" />
            ))}
          </div>
        </section>

        {/* Featured Products Skeleton */}
        <section>
          <div className="h-10 w-56 bg-white/10 rounded-lg mb-6" />
          <CardSkeleton count={4} />
        </section>
      </div>
    </div>
  )
}
