export default function MaturityReportLoading() {
  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <div className="animate-pulse space-y-8">
        <div className="flex gap-2 items-center">
          <div className="h-4 w-16 bg-white/5 rounded" />
          <div className="h-4 w-4 bg-white/5 rounded" />
          <div className="h-4 w-24 bg-white/5 rounded" />
        </div>
        <div className="space-y-4">
          <div className="h-7 w-32 bg-green-500/10 border border-green-500/20 rounded-lg" />
          <div className="h-12 w-3/4 bg-white/10 rounded-lg" />
          <div className="h-5 w-2/3 bg-white/5 rounded" />
        </div>
        <div className="aspect-[16/9] w-full rounded-2xl border border-white/10 bg-white/5" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl bg-white/[0.03] border border-white/5" />
          ))}
        </div>
      </div>
    </div>
  )
}
