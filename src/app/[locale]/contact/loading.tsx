export default function ContactLoading() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-8">
        {/* Header Skeleton */}
        <div className="text-center space-y-4">
          <div className="h-12 w-64 mx-auto bg-white/10 rounded-lg" />
          <div className="h-6 w-96 mx-auto bg-white/5 rounded-lg" />
        </div>

        {/* Contact Form Skeleton */}
        <div className="p-8 rounded-2xl bg-white/5 border border-white/5 space-y-6">
          {/* Form Fields */}
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="space-y-2">
              <div className="h-5 w-24 bg-white/5 rounded" />
              <div className={`h-${i === 3 ? '32' : '12'} w-full bg-white/5 border border-white/5 rounded-lg`} />
            </div>
          ))}

          {/* Submit Button Skeleton */}
          <div className="h-12 w-full bg-indigo-500/20 rounded-lg" />
        </div>

        {/* Contact Info Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="text-center p-6 rounded-xl bg-white/5 border border-white/5 space-y-3">
              <div className="h-12 w-12 mx-auto bg-indigo-500/20 rounded-full" />
              <div className="h-5 w-24 mx-auto bg-white/5 rounded" />
              <div className="h-4 w-32 mx-auto bg-white/5 rounded" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
