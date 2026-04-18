/**
 * LoadingSkeleton Component
 *
 * Skeleton screens for content loading states.
 * Provides visual continuity during data fetch.
 *
 * @see doc/design/LOADING_STATES_GUIDE.md
 */

import React from 'react'

interface LoadingSkeletonProps {
  variant?: 'card' | 'table-row' | 'text' | 'avatar' | 'custom'
  width?: string
  height?: string
  className?: string
  count?: number
  animate?: boolean
}

export function LoadingSkeleton({
  variant = 'text',
  width,
  height,
  className = '',
  count = 1,
  animate = true,
}: LoadingSkeletonProps) {
  const baseClasses = `bg-white/5 rounded ${animate ? 'animate-pulse' : ''}`

  const variantClasses = {
    card: 'h-64 w-full',
    'table-row': 'h-12 w-full',
    text: 'h-4 w-full',
    avatar: 'h-10 w-10 rounded-full',
    custom: '',
  }

  const sizeStyles = {
    width: width || undefined,
    height: height || undefined,
  }

  const skeletonClass = `${baseClasses} ${variantClasses[variant]} ${className}`

  if (count === 1) {
    return (
      <div
        className={skeletonClass}
        style={sizeStyles}
        role="status"
        aria-label="Loading..."
      >
        <span className="sr-only">Loading...</span>
      </div>
    )
  }

  return (
    <div className="space-y-3" role="status" aria-label="Loading...">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={skeletonClass}
          style={sizeStyles}
        />
      ))}
      <span className="sr-only">Loading...</span>
    </div>
  )
}

// Additional specialized components...
export function CardSkeleton({ count = 1 }: { count?: number }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
      <div className="space-y-4">
        <LoadingSkeleton variant="text" width="60%" height="1.5rem" />
        <LoadingSkeleton variant="text" count={3} />
      </div>
    </div>
  )
}

export function ListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="p-4 rounded-xl bg-white/5 border border-white/5 flex items-center gap-4">
          <div className="h-10 w-10 bg-white/5 rounded-lg shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-48 bg-white/5 rounded" />
            <div className="h-3 w-32 bg-white/5 rounded" />
          </div>
          <div className="h-8 w-20 bg-white/5 rounded-lg" />
        </div>
      ))}
    </div>
  )
}

export default LoadingSkeleton
