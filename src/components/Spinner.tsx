interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  variant?: 'primary' | 'white' | 'gray'
  label?: string
  className?: string
}

export default function Spinner({
  size = 'md',
  variant = 'primary',
  label = 'Loading...',
  className = '',
}: SpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-2',
    lg: 'w-12 h-12 border-3',
    xl: 'w-16 h-16 border-4',
  }

  const variantClasses = {
    primary: 'border-indigo-600 border-t-transparent',
    white: 'border-white border-t-transparent',
    gray: 'border-gray-400 border-t-transparent',
  }

  return (
    <div
      className={`inline-block ${sizeClasses[size]} ${variantClasses[variant]} rounded-full animate-spin ${className}`}
      role="status"
      aria-label={label}
      aria-live="polite"
    >
      <span className="sr-only">{label}</span>
    </div>
  )
}

export function SpinnerOverlay({ label = 'Loading...' }: { label?: string }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/80 backdrop-blur-sm"
      role="status"
      aria-label={label}
      aria-live="polite"
    >
      <div className="flex flex-col items-center gap-4">
        <Spinner size="xl" variant="white" label={label} />
        <p className="text-white text-lg font-medium">{label}</p>
      </div>
    </div>
  )
}

export function ButtonSpinner({ label = 'Processing...' }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <Spinner size="sm" variant="white" label={label} />
      <span>{label}</span>
    </span>
  )
}
