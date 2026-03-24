/**
 * QueryPreview Component
 *
 * Displays a preview of content matching the current query filters.
 * Shows total count, source/status breakdowns, and sample titles.
 * Collapsed by default, showing first 3 titles with "Show all" expand.
 */

import * as React from "react"
import { Loader2, ChevronDown, ChevronUp } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { ContentQueryPreview as PreviewData } from "@/types/query"

interface QueryPreviewProps {
  preview: PreviewData | undefined
  isLoading: boolean
  error: Error | null
  onRetry?: () => void
}

export function QueryPreview({
  preview,
  isLoading,
  error,
  onRetry,
}: QueryPreviewProps) {
  const [expanded, setExpanded] = React.useState(false)

  if (isLoading) {
    return (
      <div className="bg-muted/30 flex items-center gap-2 rounded-md border p-3">
        <Loader2 className="text-muted-foreground h-4 w-4 animate-spin" />
        <span className="text-muted-foreground text-sm">
          Loading preview...
        </span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="border-destructive/50 bg-destructive/5 rounded-md border p-3">
        <p className="text-destructive text-sm">Failed to load preview</p>
        {onRetry && (
          <Button
            variant="ghost"
            size="sm"
            className="mt-1 h-7 text-xs"
            onClick={onRetry}
          >
            Retry
          </Button>
        )}
      </div>
    )
  }

  if (!preview) return null

  if (preview.total_count === 0) {
    return (
      <div className="bg-muted/30 rounded-md border p-3">
        <p className="text-muted-foreground text-sm">
          No content matches the current filters.
        </p>
      </div>
    )
  }

  const visibleTitles = expanded
    ? preview.sample_titles
    : preview.sample_titles.slice(0, 3)
  const hasMoreTitles = preview.sample_titles.length > 3

  return (
    <div className="bg-muted/30 space-y-2 rounded-md border p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">
          {preview.total_count} item{preview.total_count !== 1 ? "s" : ""} match
        </span>
        {preview.date_range.earliest && preview.date_range.latest && (
          <span className="text-muted-foreground text-xs">
            {preview.date_range.earliest.slice(0, 10)} -{" "}
            {preview.date_range.latest.slice(0, 10)}
          </span>
        )}
      </div>

      {/* Source breakdown */}
      {Object.keys(preview.by_source).length > 0 && (
        <div className="flex flex-wrap gap-1">
          {Object.entries(preview.by_source).map(([source, count]) => (
            <Badge key={source} variant="outline" className="text-xs">
              {source}: {count}
            </Badge>
          ))}
        </div>
      )}

      {/* Sample titles */}
      {visibleTitles.length > 0 && (
        <div className="space-y-1">
          <span className="text-muted-foreground text-xs">Sample titles:</span>
          <ul id="sample-titles-list" className="space-y-0.5">
            {visibleTitles.map((title, i) => (
              <li key={i} className="text-foreground/80 truncate text-xs">
                {title}
              </li>
            ))}
          </ul>
          {hasMoreTitles && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 p-0 text-xs"
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
              aria-controls="sample-titles-list"
            >
              {expanded ? (
                <>
                  <ChevronUp className="mr-1 h-3 w-3" />
                  Show less
                </>
              ) : (
                <>
                  <ChevronDown className="mr-1 h-3 w-3" />
                  Show all {preview.sample_titles.length}
                </>
              )}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
