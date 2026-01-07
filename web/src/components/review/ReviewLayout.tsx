/**
 * ReviewLayout Component
 *
 * Main layout for the review page with:
 * - Two-column responsive grid for source and generated content
 * - Feedback panel at the bottom
 * - Optional header with navigation
 *
 * On mobile, switches to stacked layout with tabs.
 */

import * as React from "react"
import { cn } from "@/lib/utils"
import type { ReviewLayoutProps } from "@/types/review"

export function ReviewLayout({
  leftPane,
  rightPane,
  feedbackPanel,
  header,
}: ReviewLayoutProps) {
  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      {/* Header */}
      {header}

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden lg:flex-row">
        {/* Left pane - Source content */}
        <div className="flex flex-1 flex-col overflow-hidden border-b lg:border-b-0 lg:border-r">
          {leftPane}
        </div>

        {/* Right pane - Generated content */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {rightPane}
        </div>
      </div>

      {/* Feedback panel at bottom */}
      {feedbackPanel && (
        <div className="shrink-0 border-t bg-muted/30">
          {feedbackPanel}
        </div>
      )}
    </div>
  )
}

/**
 * ReviewPaneHeader - Header for each pane showing the pane title
 */
interface ReviewPaneHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  className?: string
}

export function ReviewPaneHeader({
  title,
  subtitle,
  actions,
  className,
}: ReviewPaneHeaderProps) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-between border-b bg-muted/30 px-4 py-2",
        className
      )}
    >
      <div>
        <h3 className="text-sm font-medium">{title}</h3>
        {subtitle && (
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
