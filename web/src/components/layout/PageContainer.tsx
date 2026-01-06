/**
 * PageContainer Component
 *
 * Provides consistent layout and spacing for page content.
 * Use this as the wrapper for all page components.
 *
 * Features:
 * - Consistent padding and max-width
 * - Optional page title and description
 * - Action slot for page-level buttons
 * - Responsive adjustments
 *
 * @example
 * // Basic usage
 * <PageContainer>
 *   <p>Page content here</p>
 * </PageContainer>
 *
 * @example
 * // With title and actions
 * <PageContainer
 *   title="Newsletters"
 *   description="Manage ingested newsletters"
 *   actions={<Button>Ingest New</Button>}
 * >
 *   <NewsletterList />
 * </PageContainer>
 */

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Props for the PageContainer component
 */
interface PageContainerProps {
  /** Page title (displayed as h1) */
  title?: string
  /** Page description/subtitle */
  description?: string
  /** Action buttons to display in the header */
  actions?: React.ReactNode
  /** Main page content */
  children: React.ReactNode
  /** Additional CSS classes for the container */
  className?: string
  /** Additional CSS classes for the content area */
  contentClassName?: string
  /** Whether to use full width (no max-width constraint) */
  fullWidth?: boolean
}

/**
 * PageContainer component
 *
 * Wraps page content with consistent styling.
 */
export function PageContainer({
  title,
  description,
  actions,
  children,
  className,
  contentClassName,
  fullWidth = false,
}: PageContainerProps) {
  return (
    <div
      className={cn(
        // Base styles - full height with scrolling
        "flex flex-1 flex-col overflow-auto",
        className
      )}
    >
      {/* Page header with title and actions */}
      {(title || actions) && (
        <div className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div
            className={cn(
              "flex items-center justify-between px-6 py-4",
              !fullWidth && "mx-auto max-w-7xl"
            )}
          >
            <div>
              {title && (
                <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
              )}
              {description && (
                <p className="mt-1 text-sm text-muted-foreground">
                  {description}
                </p>
              )}
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        </div>
      )}

      {/* Main content area */}
      <div
        className={cn(
          "flex-1 px-6 py-6",
          !fullWidth && "mx-auto w-full max-w-7xl",
          contentClassName
        )}
      >
        {children}
      </div>
    </div>
  )
}

/**
 * PageSection component
 *
 * A section within a page with optional title.
 * Useful for organizing page content into logical groups.
 *
 * @example
 * <PageContainer title="Dashboard">
 *   <PageSection title="Recent Activity">
 *     <ActivityList />
 *   </PageSection>
 *   <PageSection title="Statistics">
 *     <StatsGrid />
 *   </PageSection>
 * </PageContainer>
 */
interface PageSectionProps {
  /** Section title */
  title?: string
  /** Section description */
  description?: string
  /** Section content */
  children: React.ReactNode
  /** Additional CSS classes */
  className?: string
}

export function PageSection({
  title,
  description,
  children,
  className,
}: PageSectionProps) {
  return (
    <section className={cn("mb-8 last:mb-0", className)}>
      {(title || description) && (
        <div className="mb-4">
          {title && <h2 className="text-lg font-semibold">{title}</h2>}
          {description && (
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  )
}
