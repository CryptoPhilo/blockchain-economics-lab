export default function CmcRankBadge({ rank }: { rank: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center rounded border border-white/10 bg-white/[0.04] px-1 py-0.5 text-[9px] font-semibold leading-none text-slate-400 sm:px-1.5 sm:text-[10px]"
      title={`CoinMarketCap #${rank}`}
    >
      CMC #{rank}
    </span>
  )
}
