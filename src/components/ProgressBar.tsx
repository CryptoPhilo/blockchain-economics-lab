interface ProgressBarProps {
  progress: number // 0-100
  label?: string
  showPercentage?: boolean
  variant?: 'primary' | 'success' | 'warning' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export default function ProgressBar({
  progress,
  label,
  showPercentage = false,
  variant = 'primary',
  size = 'md',
  className = '',
}: ProgressBarProps) {
  const clampedProgress = Math.max(0, Math.min(100, progress))

  const sizeClasses = {
    sm: 'h-2',
    md: 'h-3',
    lg: 'h-4',
  }

  const variantClasses = {
    primary: 'bg-indigo-600',
    success: 'bg-green-600',
    warning: 'bg-yellow-600',
    danger: 'bg-red-600',
  }

  return (
    <div className={`w-full ${className}`}>
      {(label || showPercentage) && (
        <div className="flex items-center justify-between mb-2 text-sm">
          {label && <span className="text-gray-400">{label}</span>}
          {showPercentage && (
            <span className="text-white font-medium">
              {Math.round(clampedProgress)}%
            </span>
          )}
        </div>
      )}

      <div
        className={`w-full ${sizeClasses[size]} bg-white/10 rounded-full overflow-hidden`}
        role="progressbar"
        aria-valuenow={clampedProgress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label || 'Progress'}
      >
        <div
          className={`${sizeClasses[size]} ${variantClasses[variant]} rounded-full transition-all duration-300 ease-out`}
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
    </div>
  )
}

export function StepProgressBar({
  currentStep,
  totalSteps,
  steps,
}: {
  currentStep: number
  totalSteps: number
  steps?: string[]
}) {
  return (
    <div className="w-full">
      {/* Step indicators */}
      {steps && steps.length === totalSteps && (
        <div className="flex justify-between mb-4">
          {steps.map((step, index) => {
            const stepNumber = index + 1
            const isComplete = stepNumber < currentStep
            const isCurrent = stepNumber === currentStep
            const isUpcoming = stepNumber > currentStep

            return (
              <div
                key={index}
                className="flex flex-col items-center flex-1"
              >
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold text-sm mb-2 transition-all ${
                    isComplete
                      ? 'bg-green-600 text-white'
                      : isCurrent
                      ? 'bg-indigo-600 text-white ring-4 ring-indigo-600/30'
                      : 'bg-white/10 text-gray-500'
                  }`}
                >
                  {isComplete ? '✓' : stepNumber}
                </div>
                <span
                  className={`text-xs text-center ${
                    isCurrent ? 'text-white font-medium' : 'text-gray-500'
                  }`}
                >
                  {step}
                </span>
                {index < steps.length - 1 && (
                  <div className="absolute h-0.5 w-full bg-white/10 top-5 left-1/2 -z-10">
                    <div
                      className={`h-full bg-green-600 transition-all duration-500 ${
                        isComplete ? 'w-full' : 'w-0'
                      }`}
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Progress bar */}
      <ProgressBar
        progress={(currentStep / totalSteps) * 100}
        label={`Step ${currentStep} of ${totalSteps}`}
        showPercentage
        variant="primary"
      />
    </div>
  )
}
