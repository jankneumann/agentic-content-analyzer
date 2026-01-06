/**
 * Newsletter React Query Hooks
 *
 * Custom hooks for fetching and mutating newsletter data.
 * Built on TanStack Query for caching, background updates,
 * and optimistic updates.
 *
 * @example
 * // Fetch newsletters list
 * const { data, isLoading } = useNewsletters({ status: 'completed' })
 *
 * @example
 * // Fetch single newsletter
 * const { data: newsletter } = useNewsletter(id)
 *
 * @example
 * // Trigger ingestion
 * const { mutate: ingest } = useIngestNewsletters()
 * ingest({ source: 'gmail' })
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchNewsletters,
  fetchNewsletter,
  fetchNewsletterWithSummary,
  ingestNewsletters,
  deleteNewsletter,
  fetchNewsletterStats,
} from "@/lib/api/newsletters"
import type { NewsletterFilters, IngestRequest } from "@/types"

/**
 * Hook to fetch paginated list of newsletters
 *
 * @param filters - Optional filters (status, source, date range, etc.)
 * @returns Query result with newsletters data
 *
 * @example
 * const { data, isLoading, error } = useNewsletters({
 *   status: 'completed',
 *   source: 'gmail',
 *   limit: 20,
 * })
 */
export function useNewsletters(filters?: NewsletterFilters) {
  return useQuery({
    queryKey: queryKeys.newsletters.list(filters),
    queryFn: () => fetchNewsletters(filters),
  })
}

/**
 * Hook to fetch a single newsletter by ID
 *
 * @param id - Newsletter ID
 * @param options - Additional query options
 * @returns Query result with newsletter data
 *
 * @example
 * const { data: newsletter } = useNewsletter(newsletterId)
 */
export function useNewsletter(
  id: string,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.newsletters.detail(id),
    queryFn: () => fetchNewsletter(id),
    enabled: options?.enabled ?? !!id,
  })
}

/**
 * Hook to fetch newsletter with its summary
 *
 * Combines newsletter and summary data in a single query.
 * Useful for detail views that need both.
 *
 * @param id - Newsletter ID
 * @returns Query result with newsletter and summary
 */
export function useNewsletterWithSummary(id: string) {
  return useQuery({
    queryKey: queryKeys.newsletters.withSummary(id),
    queryFn: () => fetchNewsletterWithSummary(id),
    enabled: !!id,
  })
}

/**
 * Hook to fetch newsletter statistics
 *
 * @returns Query result with stats by status and source
 */
export function useNewsletterStats() {
  return useQuery({
    queryKey: [...queryKeys.newsletters.all, "stats"],
    queryFn: fetchNewsletterStats,
  })
}

/**
 * Hook to trigger newsletter ingestion
 *
 * @returns Mutation object with mutate function
 *
 * @example
 * const { mutate, isPending } = useIngestNewsletters()
 *
 * // Trigger ingestion
 * mutate({ source: 'gmail', maxItems: 10 }, {
 *   onSuccess: (data) => {
 *     toast.success(`Ingested ${data.ingestedCount} newsletters`)
 *   },
 *   onError: (error) => {
 *     toast.error(error.message)
 *   },
 * })
 */
export function useIngestNewsletters() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: IngestRequest) => ingestNewsletters(request),
    onSuccess: () => {
      // Invalidate newsletter list to show new items
      queryClient.invalidateQueries({
        queryKey: queryKeys.newsletters.lists(),
      })
    },
  })
}

/**
 * Hook to delete a newsletter
 *
 * @returns Mutation object with mutate function
 *
 * @example
 * const { mutate: deleteNl } = useDeleteNewsletter()
 * deleteNl(newsletterId)
 */
export function useDeleteNewsletter() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteNewsletter,
    onSuccess: (_data, id) => {
      // Remove from cache
      queryClient.removeQueries({
        queryKey: queryKeys.newsletters.detail(id),
      })
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: queryKeys.newsletters.lists(),
      })
    },
  })
}

/**
 * Hook to prefetch newsletters for navigation
 *
 * Use this to prefetch data before navigating to a page.
 *
 * @example
 * const prefetch = usePrefetchNewsletters()
 *
 * // On hover or focus
 * <Link onMouseEnter={() => prefetch({ status: 'completed' })}>
 *   View Newsletters
 * </Link>
 */
export function usePrefetchNewsletters() {
  const queryClient = useQueryClient()

  return (filters?: NewsletterFilters) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.newsletters.list(filters),
      queryFn: () => fetchNewsletters(filters),
    })
  }
}

/**
 * Hook to prefetch a single newsletter
 *
 * @example
 * const prefetch = usePrefetchNewsletter()
 * prefetch(newsletterId)
 */
export function usePrefetchNewsletter() {
  const queryClient = useQueryClient()

  return (id: string) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.newsletters.detail(id),
      queryFn: () => fetchNewsletter(id),
    })
  }
}
