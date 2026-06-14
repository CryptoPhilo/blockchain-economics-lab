type BrandMarkProps = {
  size?: 'sm' | 'md'
}

export default function BrandMark({ size = 'md' }: BrandMarkProps) {
  const boxSize = size === 'sm' ? 'h-8 w-8' : 'h-9 w-9'
  const svgSize = size === 'sm' ? 'h-7 w-7' : 'h-8 w-8'

  return (
    <span
      aria-label="BCE Lab"
      className={`${boxSize} relative flex shrink-0 items-center justify-center overflow-hidden rounded-md border border-cyan-300/25 bg-slate-950 shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_12px_30px_rgba(14,165,233,0.18)]`}
    >
      <svg viewBox="0 0 36 36" aria-hidden="true" className={svgSize}>
        <path d="M10 28V8h9.2c4.1 0 6.7 2 6.7 5.1 0 1.8-.9 3.2-2.5 4 2.2.7 3.6 2.4 3.6 4.8 0 3.7-2.9 6.1-7.4 6.1H10Z" fill="#f8fafc" />
        <path d="M14.5 16h4.1c1.5 0 2.4-.7 2.4-1.9 0-1.1-.9-1.8-2.4-1.8h-4.1V16Zm0 7.7h4.8c1.7 0 2.7-.8 2.7-2.1 0-1.4-1-2.2-2.8-2.2h-4.7v4.3Z" fill="#020617" />
        <circle cx="27.5" cy="8.5" r="2.2" fill="#22d3ee" />
        <circle cx="28.5" cy="27.5" r="2.2" fill="#34d399" />
        <path d="M25.8 10.2 22.8 14M23.6 22.7l3.2 3.1" stroke="#38bdf8" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    </span>
  )
}
