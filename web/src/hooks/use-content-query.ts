/**
 * Content Query React Query Hook
 *
 * Custom hook for previewing content query results.
 * Uses TanStack Query with 2s staleTime to avoid excessive
 * preview requests while filters are being adjusted.
 *
 * @example
 * const { data: preview, isLoading } = useContentQueryPreview(query, hasFilters)
 */

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import { previewContentQuery } from "@/lib/api/query"
import type { ContentQuery } from "@/types/query"

/**
 * Check if a ContentQuery has any active filters
 */
function hasActiveFilters(query: ContentQuery): boolean {
  return !!(
    query.source_types?.length ||
    query.statuses?.length ||
    query.publications?.length ||
    query.publication_search ||
    query.start_date ||
    query.end_date ||
    query.search ||
    query.limit
  )
}

/**
 * Hook to preview content matching a query
 *
 * Only fetches when filters are active (enabled parameter).
 * Uses 2s staleTime to debounce while user adjusts filters.
 *
 * @param query - Content query filters
 * @param enabled - Explicit enable/disable (defaults to hasActiveFilters)
 * @returns Query result with ContentQueryPreview
 */
export function useContentQueryPreview(
  query: ContentQuery,
  enabled?: boolean
) {
  const isEnabled = enabled ?? hasActiveFilters(query)

  return useQuery({
    queryKey: queryKeys.contents.queryPreview(query),
    queryFn: () => previewContentQuery(query),
    enabled: isEnabled,
    staleTime: 2000,
  })
}
