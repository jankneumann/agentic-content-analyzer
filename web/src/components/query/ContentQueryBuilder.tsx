/**
 * ContentQueryBuilder Component
 *
 * Main composable component for building content query filters.
 * Composes SourceFilter, StatusFilter, DateRangeFilter, and QueryPreview.
 *
 * Used in summarize and digest dialogs to filter content before operations.
 *
 * @example
 * <ContentQueryBuilder
 *   defaultQuery={{ statuses: ["pending", "parsed"] }}
 *   onChange={(query) => setQuery(query)}
 *   showPreview
 * />
 */

import * as React from "react"
import { Filter, Search } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Button } from "@/components/ui/button"
import { SourceFilter } from "./SourceFilter"
import { StatusFilter } from "./StatusFilter"
import { DateRangeFilter } from "./DateRangeFilter"
import { FilterChip } from "./FilterChip"
import { QueryPreview } from "./QueryPreview"
import { useContentQueryPreview } from "@/hooks/use-content-query"
import type { ContentQuery } from "@/types/query"
import type { ContentSource, ContentStatus } from "@/types"

interface ContentQueryBuilderProps {
  /** Default query values */
  defaultQuery?: ContentQuery
  /** Called when query changes */
  onChange: (query: ContentQuery) => void
  /** Show live preview of matching content */
  showPreview?: boolean
}

export function ContentQueryBuilder({
  defaultQuery,
  onChange,
  showPreview = true,
}: ContentQueryBuilderProps) {
  const [sourcesOpen, setSourcesOpen] = React.useState(false)
  const [statusOpen, setStatusOpen] = React.useState(false)
  const [dateOpen, setDateOpen] = React.useState(false)

  // Filter state
  const [sourceTypes, setSourceTypes] = React.useState<ContentSource[]>(
    defaultQuery?.source_types ?? []
  )
  const [statuses, setStatuses] = React.useState<ContentStatus[]>(
    defaultQuery?.statuses ?? []
  )
  const [startDate, setStartDate] = React.useState(defaultQuery?.start_date ?? "")
  const [endDate, setEndDate] = React.useState(defaultQuery?.end_date ?? "")
  const [search, setSearch] = React.useState(defaultQuery?.search ?? "")
  const [publication, setPublication] = React.useState(
    defaultQuery?.publication_search ?? ""
  )

  // Build current query
  const currentQuery: ContentQuery = React.useMemo(() => {
    const q: ContentQuery = {}
    if (sourceTypes.length > 0) q.source_types = sourceTypes
    if (statuses.length > 0) q.statuses = statuses
    if (startDate) q.start_date = new Date(startDate).toISOString()
    if (endDate) q.end_date = new Date(endDate + "T23:59:59").toISOString()
    if (search.trim()) q.search = search.trim()
    if (publication.trim()) q.publication_search = publication.trim()
    return q
  }, [sourceTypes, statuses, startDate, endDate, search, publication])

  // Notify parent of changes
  React.useEffect(() => {
    onChange(currentQuery)
  }, [currentQuery, onChange])

  // Preview hook
  const hasFilters =
    sourceTypes.length > 0 ||
    statuses.length > 0 ||
    !!startDate ||
    !!endDate ||
    !!search.trim() ||
    !!publication.trim()

  const {
    data: preview,
    isLoading: previewLoading,
    error: previewError,
    refetch: retryPreview,
  } = useContentQueryPreview(currentQuery, showPreview && hasFilters)

  return (
    <div className="space-y-3">
      {/* Active filter chips */}
      {hasFilters && (
        <div className="flex flex-wrap gap-1.5">
          {sourceTypes.length > 0 && (
            <FilterChip
              label="Sources"
              value={sourceTypes.join(", ")}
              onRemove={() => setSourceTypes([])}
            />
          )}
          {statuses.length > 0 && (
            <FilterChip
              label="Status"
              value={statuses.join(", ")}
              onRemove={() => setStatuses([])}
            />
          )}
          {startDate && (
            <FilterChip
              label="After"
              value={startDate}
              onRemove={() => setStartDate("")}
            />
          )}
          {endDate && (
            <FilterChip
              label="Before"
              value={endDate}
              onRemove={() => setEndDate("")}
            />
          )}
          {search.trim() && (
            <FilterChip
              label="Search"
              value={search}
              onRemove={() => setSearch("")}
            />
          )}
          {publication.trim() && (
            <FilterChip
              label="Publication"
              value={publication}
              onRemove={() => setPublication("")}
            />
          )}
        </div>
      )}

      {/* Filter sections */}
      <div className="space-y-2">
        {/* Source filter */}
        <Collapsible open={sourcesOpen} onOpenChange={setSourcesOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="w-full justify-start h-8 text-sm">
              <Filter className="h-3.5 w-3.5 mr-2" />
              Source Types
              {sourceTypes.length > 0 && (
                <span className="ml-auto text-xs text-muted-foreground">
                  {sourceTypes.length} selected
                </span>
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2">
            <SourceFilter selected={sourceTypes} onChange={setSourceTypes} />
          </CollapsibleContent>
        </Collapsible>

        {/* Status filter */}
        <Collapsible open={statusOpen} onOpenChange={setStatusOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="w-full justify-start h-8 text-sm">
              <Filter className="h-3.5 w-3.5 mr-2" />
              Status
              {statuses.length > 0 && (
                <span className="ml-auto text-xs text-muted-foreground">
                  {statuses.length} selected
                </span>
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2">
            <StatusFilter selected={statuses} onChange={setStatuses} />
          </CollapsibleContent>
        </Collapsible>

        {/* Date range filter */}
        <Collapsible open={dateOpen} onOpenChange={setDateOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="w-full justify-start h-8 text-sm">
              <Filter className="h-3.5 w-3.5 mr-2" />
              Date Range
              {(startDate || endDate) && (
                <span className="ml-auto text-xs text-muted-foreground">
                  {startDate || "..."} - {endDate || "..."}
                </span>
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2">
            <DateRangeFilter
              startDate={startDate}
              endDate={endDate}
              onStartDateChange={setStartDate}
              onEndDateChange={setEndDate}
            />
          </CollapsibleContent>
        </Collapsible>

        {/* Text search */}
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground flex items-center gap-1">
              <Search className="h-3 w-3" />
              Title search
            </Label>
            <Input
              placeholder="Search titles..."
              value={search}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Publication</Label>
            <Input
              placeholder="Filter by publication..."
              value={publication}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPublication(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
        </div>
      </div>

      {/* Preview */}
      {showPreview && hasFilters && (
        <QueryPreview
          preview={preview}
          isLoading={previewLoading}
          error={previewError}
          onRetry={() => retryPreview()}
        />
      )}
    </div>
  )
}
