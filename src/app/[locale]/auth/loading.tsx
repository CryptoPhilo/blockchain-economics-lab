export default function AuthLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="animate-pulse space-y-6">
          {/* Logo Skeleton */}
          <div className="text-center">
            <div className="h-12 w-12 mx-auto bg-indigo-500/20 rounded-xl mb-4" />
            <div className="h-8 w-48 mx-auto bg-white/10 rounded-lg" />
          </div>

          {/* Auth Card Skeleton */}
          <div className="p-8 rounded-2xl bg-white/5 border border-white/5 space-y-6">
            {/* Tabs Skeleton */}
            <div className="flex gap-2 p-1 bg-white/5 rounded-lg">
              {Array.from({ length: 2 }, (_, i) => (
                <div key={i} className="flex-1 h-10 bg-white/5 rounded-lg" />
              ))}
            </div>

            {/* Form Fields Skeleton */}
            {Array.from({ length: 2 }, (_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-5 w-20 bg-white/5 rounded" />
                <div className="h-12 w-full bg-white/5 border border-white/5 rounded-lg" />
              </div>
            ))}

            {/* Submit Button Skeleton */}
            <div className="h-12 w-full bg-indigo-500/20 rounded-lg" />

            {/* Divider */}
            <div className="flex items-center gap-4">
              <div className="flex-1 h-px bg-white/5" />
              <div className="h-4 w-16 bg-white/5 rounded" />
              <div className="flex-1 h-px bg-white/5" />
            </div>

            {/* Social Login Skeleton */}
            <div className="h-12 w-full bg-white/5 border border-white/5 rounded-lg" />
          </div>

          {/* Terms Text Skeleton */}
          <div className="text-center space-y-2">
            <div className="h-4 w-full max-w-sm mx-auto bg-white/5 rounded" />
            <div className="h-4 w-64 mx-auto bg-white/5 rounded" />
          </div>
        </div>
      </div>
    </div>
  )
}
