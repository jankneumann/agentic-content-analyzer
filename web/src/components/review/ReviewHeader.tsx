/**
 * ReviewHeader Component
 *
 * Header for the review page with:
 * - Back navigation
 * - Page title
 * - Mini-nav for prev/next item navigation
 */

import { Link } from "@tanstack/react-router"
import { ArrowLeft, ChevronLeft, ChevronRight, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { ReviewHeaderProps } from "@/types/review"

export function ReviewHeader({
  title,
  backLabel,
  backTo,
  navigation,
  isNavigationLoading,
  onPrevious,
  onNext,
}: ReviewHeaderProps) {
  const hasPrevious = navigation?.prevId !== null
  const hasNext = navigation?.nextId !== null

  return (
    <div className="flex shrink-0 items-center justify-between border-b bg-background px-4 py-3">
      {/* Back button */}
      <Link to={backTo}>
        <Button
          variant="ghost"
          size="sm"
          className="gap-2"
          aria-label={backLabel}
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="hidden sm:inline">{backLabel}</span>
        </Button>
      </Link>

      {/* Title */}
      <h1 className="text-lg font-semibold">{title}</h1>

      {/* Mini navigation */}
      <div className="flex items-center gap-1">
        {isNavigationLoading ? (
          <div className="flex items-center gap-2 px-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
          </div>
        ) : navigation ? (
          <>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              disabled={!hasPrevious}
              onClick={onPrevious}
              aria-label="Previous item"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            <span className="min-w-[60px] text-center text-sm text-muted-foreground">
              {navigation.position} of {navigation.total}
            </span>

            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              disabled={!hasNext}
              onClick={onNext}
              aria-label="Next item"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </>
        ) : (
          // Placeholder for layout consistency when no navigation
          <div className="w-[120px]" />
        )}
      </div>
    </div>
  )
}
