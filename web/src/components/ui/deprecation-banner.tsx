/**
 * Deprecation Banner Component
 *
 * Displays a warning banner indicating that a feature or page is deprecated.
 * Used during the phased deprecation of legacy features.
 *
 * @example
 * <DeprecationBanner
 *   title="This page is deprecated"
 *   message="Use the Content page instead for managing all ingested content."
 *   linkText="Go to Content"
 *   linkHref="/contents"
 * />
 */

import { AlertTriangle, ArrowRight, X } from "lucide-react"
import { useState } from "react"
import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

interface DeprecationBannerProps {
  /** Banner title */
  title: string
  /** Detailed message explaining the deprecation */
  message: string
  /** Text for the action link */
  linkText?: string
  /** URL for the action link */
  linkHref?: string
  /** Whether the banner can be dismissed */
  dismissible?: boolean
  /** Additional CSS classes */
  className?: string
}

export function DeprecationBanner({
  title,
  message,
  linkText,
  linkHref,
  dismissible = false,
  className,
}: DeprecationBannerProps) {
  const [isDismissed, setIsDismissed] = useState(false)

  if (isDismissed) {
    return null
  }

  return (
    <div
      className={cn(
        "relative rounded-lg border border-amber-200 bg-amber-50 p-4",
        "dark:border-amber-900/50 dark:bg-amber-950/30",
        className
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        {/* Warning Icon */}
        <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-500" />

        {/* Content */}
        <div className="flex-1 space-y-1">
          <h4 className="font-medium text-amber-800 dark:text-amber-200">
            {title}
          </h4>
          <p className="text-sm text-amber-700 dark:text-amber-300">
            {message}
          </p>

          {/* Action Link */}
          {linkText && linkHref && (
            <Link
              to={linkHref}
              className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-amber-800 underline-offset-4 hover:underline dark:text-amber-200"
            >
              {linkText}
              <ArrowRight className="h-4 w-4" />
            </Link>
          )}
        </div>

        {/* Dismiss Button */}
        {dismissible && (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0 text-amber-600 hover:bg-amber-100 hover:text-amber-800 dark:text-amber-400 dark:hover:bg-amber-900/50 dark:hover:text-amber-200"
            onClick={() => setIsDismissed(true)}
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Dismiss</span>
          </Button>
        )}
      </div>
    </div>
  )
}
