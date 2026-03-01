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

export function QueryPreview({ preview, isLoading, error, onRetry }: QueryPreviewProps) {
  const [expanded, setExpanded] = React.useState(false)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-md border p-3 bg-muted/30">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Loading preview...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/50 p-3 bg-destructive/5">
        <p className="text-sm text-destructive">Failed to load preview</p>
        {onRetry && (
          <Button variant="ghost" size="sm" className="mt-1 h-7 text-xs" onClick={onRetry}>
            Retry
          </Button>
        )}
      </div>
    )
  }

  if (!preview) return null

  if (preview.total_count === 0) {
    return (
      <div className="rounded-md border p-3 bg-muted/30">
        <p className="text-sm text-muted-foreground">No content matches the current filters.</p>
      </div>
    )
  }

  const visibleTitles = expanded ? preview.sample_titles : preview.sample_titles.slice(0, 3)
  const hasMoreTitles = preview.sample_titles.length > 3

  return (
    <div className="space-y-2 rounded-md border p-3 bg-muted/30">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">
          {preview.total_count} item{preview.total_count !== 1 ? "s" : ""} match
        </span>
        {preview.date_range.earliest && preview.date_range.latest && (
          <span className="text-xs text-muted-foreground">
            {preview.date_range.earliest.slice(0, 10)} - {preview.date_range.latest.slice(0, 10)}
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
          <span className="text-xs text-muted-foreground">Sample titles:</span>
          <ul className="space-y-0.5">
            {visibleTitles.map((title, i) => (
              <li key={i} className="text-xs truncate text-foreground/80">
                {title}
              </li>
            ))}
          </ul>
          {hasMoreTitles && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs p-0"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? (
                <>
                  <ChevronUp className="h-3 w-3 mr-1" />
                  Show less
                </>
              ) : (
                <>
                  <ChevronDown className="h-3 w-3 mr-1" />
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
