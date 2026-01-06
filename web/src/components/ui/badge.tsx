/**
 * Badge Component
 *
 * A small label component for displaying status, categories, or counts.
 * Commonly used for status indicators, tags, and notification counts.
 *
 * @example
 * // Default badge
 * <Badge>New</Badge>
 *
 * @example
 * // Variant badges for different states
 * <Badge variant="default">Active</Badge>
 * <Badge variant="secondary">Draft</Badge>
 * <Badge variant="destructive">Error</Badge>
 * <Badge variant="outline">v1.0.0</Badge>
 *
 * @example
 * // Status badges for pipeline steps
 * <Badge variant="default">Completed</Badge>
 * <Badge variant="secondary">Processing</Badge>
 * <Badge variant="destructive">Failed</Badge>
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Badge variants configuration
 *
 * Similar to buttonVariants, this uses cva for type-safe styling.
 * Variants are designed to convey different states or categories.
 */
const badgeVariants = cva(
  // Base classes: inline display, rounded pill shape, small text
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      /**
       * Visual style variants
       * - default: Primary color, solid background (success/active states)
       * - secondary: Muted color for less prominent badges
       * - destructive: Red color for errors or warnings
       * - outline: Transparent with border (version numbers, tags)
       */
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80",
        outline: "text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

/**
 * Badge props interface
 *
 * Extends native div attributes with variant styling.
 */
export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

/**
 * Badge component
 *
 * A simple label for status indicators and tags.
 * Does not forward ref as it's typically not needed for badges.
 */
function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
