export default function ExchangesLoading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <div className="animate-pulse space-y-6">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-10 sm:px-8">
          <div className="h-4 w-28 rounded bg-cyan-500/20" />
          <div className="mt-4 h-10 w-56 rounded bg-white/10" />
          <div className="mt-4 h-5 max-w-xl rounded bg-white/5" />
        </div>
        <div className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]">
          <div className="grid grid-cols-[minmax(0,1fr)_7rem_6rem] gap-3 border-b border-white/10 bg-white/[0.04] px-4 py-3 sm:grid-cols-[minmax(0,1fr)_10rem_8rem]">
            <div className="h-4 rounded bg-white/5" />
            <div className="h-4 rounded bg-white/5" />
            <div className="h-4 rounded bg-white/5" />
          </div>
          <div className="divide-y divide-white/5">
            {Array.from({ length: 6 }, (_, index) => (
              <div
                key={index}
                className="grid grid-cols-[minmax(0,1fr)_7rem_6rem] items-center gap-3 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_10rem_8rem]"
              >
                <div className="space-y-2">
                  <div className="h-4 w-44 rounded bg-white/10" />
                  <div className="h-3 w-20 rounded bg-white/5" />
                </div>
                <div className="h-4 rounded bg-white/5" />
                <div className="h-5 rounded bg-cyan-500/10" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
