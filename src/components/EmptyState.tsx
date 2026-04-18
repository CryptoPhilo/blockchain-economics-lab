/**
 * EmptyState Component
 *
 * User-friendly empty states with actionable guidance.
 *
 * @see doc/design/EMPTY_STATES_GUIDE.md
 */

'use client'

import React from 'react'
import Link from 'next/link'

interface EmptyStateProps {
  icon?: string
  title: string
  description?: string
  action?: {
    label: string
    href: string
  }
  secondaryAction?: {
    label: string
    href: string
  }
  variant?: 'default' | 'success' | 'info' | 'search'
  className?: string
}

const variantColors = {
  default: 'text-gray-400',
  success: 'text-green-400',
  info: 'text-blue-400',
  search: 'text-yellow-400',
}

export function EmptyState({
  icon = '📭',
  title,
  description,
  action,
  secondaryAction,
  variant = 'default',
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-12 px-6 text-center ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className={`text-6xl mb-4 ${variantColors[variant]}`}>
        {icon}
      </div>

      <h3 className="text-xl font-semibold text-white mb-2">
        {title}
      </h3>

      {description && (
        <p className="text-gray-400 max-w-md mb-6">
          {description}
        </p>
      )}

      {action && (
        <div className="flex gap-3">
          <Link
            href={action.href}
            className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors"
          >
            {action.label}
          </Link>

          {secondaryAction && (
            <Link
              href={secondaryAction.href}
              className="px-6 py-3 bg-white/5 hover:bg-white/10 text-white font-medium rounded-lg border border-white/10 transition-colors"
            >
              {secondaryAction.label}
            </Link>
          )}
        </div>
      )}
    </div>
  )
}

export default EmptyState
