/**
 * Content React Query Hooks
 *
 * Custom hooks for fetching and mutating content data.
 * Built on TanStack Query for caching, background updates,
 * and optimistic updates.
 *
 * The Content model is the unified model replacing Newsletter + Document.
 *
 * @example
 * // Fetch contents list
 * const { data, isLoading } = useContents({ source_type: 'gmail' })
 *
 * @example
 * // Fetch single content
 * const { data: content } = useContent(id)
 *
 * @example
 * // Create content
 * const { mutate: create } = useCreateContent()
 * create({ title: 'Test', markdown_content: '# Test' })
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchContents,
  fetchContent,
  fetchContentWithSummary,
  createContent,
  deleteContent,
  fetchContentStats,
  fetchContentDuplicates,
  mergeContentDuplicate,
  ingestContents,
  summarizeContents,
  trackContentSummarization,
  type IngestContentParams,
  type SummarizeContentParams,
  type ContentSummarizationProgressEvent,
} from "@/lib/api/contents"
import { useState } from "react"
import type { ContentFilters, ContentCreateRequest } from "@/types"

/**
 * Hook to fetch paginated list of contents
 *
 * @param filters - Optional filters (source_type, status, date range, etc.)
 * @returns Query result with contents data
 *
 * @example
 * const { data, isLoading, error } = useContents({
 *   source_type: 'gmail',
 *   status: 'completed',
 *   page: 1,
 *   page_size: 20,
 * })
 */
export function useContents(filters?: ContentFilters) {
  return useQuery({
    queryKey: queryKeys.contents.list(filters),
    queryFn: () => fetchContents(filters),
  })
}

/**
 * Hook to fetch a single content by ID
 *
 * @param id - Content ID
 * @param options - Additional query options
 * @returns Query result with content data
 *
 * @example
 * const { data: content } = useContent(contentId)
 */
export function useContent(
  id: string | number,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.contents.detail(id),
    queryFn: () => fetchContent(id),
    enabled: options?.enabled ?? !!id,
  })
}

/**
 * Hook to fetch content with its summary
 *
 * Combines content and summary data in a single query.
 * Useful for detail views that need both.
 *
 * @param id - Content ID
 * @returns Query result with content and summary
 */
export function useContentWithSummary(id: string | number) {
  return useQuery({
    queryKey: queryKeys.contents.withSummary(id),
    queryFn: () => fetchContentWithSummary(id),
    enabled: !!id,
  })
}

/**
 * Hook to fetch content statistics
 *
 * @returns Query result with stats by status and source
 */
export function useContentStats() {
  return useQuery({
    queryKey: queryKeys.contents.stats(),
    queryFn: fetchContentStats,
  })
}

/**
 * Hook to fetch duplicates of a content
 *
 * @param id - Content ID
 * @returns Query result with list of duplicate contents
 */
export function useContentDuplicates(id: string | number) {
  return useQuery({
    queryKey: queryKeys.contents.duplicates(id),
    queryFn: () => fetchContentDuplicates(id),
    enabled: !!id,
  })
}

/**
 * Hook to create new content
 *
 * @returns Mutation object with mutate function
 *
 * @example
 * const { mutate, isPending } = useCreateContent()
 *
 * mutate({
 *   title: 'My Content',
 *   markdown_content: '# Hello World',
 * }, {
 *   onSuccess: (data) => {
 *     toast.success(`Created content: ${data.title}`)
 *   },
 * })
 */
export function useCreateContent() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: ContentCreateRequest) => createContent(request),
    onSuccess: () => {
      // Invalidate content list to show new item
      queryClient.invalidateQueries({
        queryKey: queryKeys.contents.lists(),
      })
      // Invalidate stats
      queryClient.invalidateQueries({
        queryKey: queryKeys.contents.stats(),
      })
    },
  })
}

/**
 * Hook to trigger content ingestion from a source
 *
 * Starts a background task to ingest content from Gmail, RSS, or YouTube.
 * Returns immediately with a task ID for tracking progress.
 *
 * @returns Mutation object with mutate function
 *
 * @example
 * const { mutate: ingest, isPending } = useIngestContents()
 *
 * ingest({
 *   source: 'gmail',
 *   max_results: 50,
 *   days_back: 7,
 * }, {
 *   onSuccess: (data) => {
 *     console.log(`Started ingestion task: ${data.task_id}`)
 *   },
 * })
 */
export function useIngestContents() {
  return useMutation({
    mutationFn: (params: IngestContentParams) => ingestContents(params),
    // The actual ingestion happens in the background,
    // so we don't invalidate immediately - the UI will poll for updates
    // Caller can provide onSuccess callback that triggers polling
  })
}

/**
 * Hook to delete content
 *
 * @returns Mutation object with mutate function
 *
 * @example
 * const { mutate: deleteIt } = useDeleteContent()
 * deleteIt(contentId)
 */
export function useDeleteContent() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string | number) => deleteContent(id),
    onSuccess: (_data, id) => {
      // Remove from cache
      queryClient.removeQueries({
        queryKey: queryKeys.contents.detail(id),
      })
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: queryKeys.contents.lists(),
      })
      // Invalidate stats
      queryClient.invalidateQueries({
        queryKey: queryKeys.contents.stats(),
      })
    },
  })
}

/**
 * Hook to merge a duplicate content into the canonical
 *
 * @returns Mutation object with mutate function
 *
 * @example
 * const { mutate: merge } = useMergeContentDuplicate()
 * merge({ canonicalId: 1, duplicateId: 2 })
 */
export function useMergeContentDuplicate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      canonicalId,
      duplicateId,
    }: {
      canonicalId: string | number
      duplicateId: string | number
    }) => mergeContentDuplicate(canonicalId, duplicateId),
    onSuccess: (_data, { canonicalId }) => {
      // Invalidate duplicates list
      queryClient.invalidateQueries({
        queryKey: queryKeys.contents.duplicates(canonicalId),
      })
      // Invalidate content list
      queryClient.invalidateQueries({
        queryKey: queryKeys.contents.lists(),
      })
    },
  })
}

/**
 * Hook to prefetch contents for navigation
 *
 * @example
 * const prefetch = usePrefetchContents()
 *
 * <Link onMouseEnter={() => prefetch({ source_type: 'gmail' })}>
 *   View Contents
 * </Link>
 */
export function usePrefetchContents() {
  const queryClient = useQueryClient()

  return (filters?: ContentFilters) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.contents.list(filters),
      queryFn: () => fetchContents(filters),
    })
  }
}

/**
 * Hook to prefetch a single content
 *
 * @example
 * const prefetch = usePrefetchContent()
 * prefetch(contentId)
 */
export function usePrefetchContent() {
  const queryClient = useQueryClient()

  return (id: string | number) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.contents.detail(id),
      queryFn: () => fetchContent(id),
    })
  }
}

/**
 * Hook to trigger content summarization with SSE progress tracking
 *
 * Starts a background task to summarize content records.
 * Tracks progress via Server-Sent Events.
 *
 * @returns Mutation object with progress state
 *
 * @example
 * const { mutate: summarize, isPending, isProcessing, progress } = useSummarizeContents()
 *
 * summarize({
 *   content_ids: [1, 2, 3], // Optional: empty = all pending
 *   force: false,
 * }, {
 *   onSuccess: (result) => {
 *     console.log(`Summarized ${result.completed} items`)
 *   },
 * })
 */
export function useSummarizeContents() {
  const queryClient = useQueryClient()
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState<ContentSummarizationProgressEvent | null>(null)

  const mutation = useMutation({
    mutationFn: async (params: SummarizeContentParams) => {
      // Start the summarization task
      const response = await summarizeContents(params)

      if (response.queued_count === 0) {
        // No content to summarize
        return {
          status: "completed" as const,
          progress: 100,
          total: 0,
          processed: 0,
          completed: 0,
          failed: 0,
          current_content_id: null,
          message: response.message,
          started_at: new Date().toISOString(),
        }
      }

      // Track progress via SSE
      setIsProcessing(true)
      try {
        const finalEvent = await trackContentSummarization(
          response.task_id,
          (event) => setProgress(event)
        )
        return finalEvent
      } finally {
        setIsProcessing(false)
      }
    },
    onSuccess: () => {
      // Invalidate content list to show updated statuses
      queryClient.invalidateQueries({
        queryKey: queryKeys.contents.lists(),
      })
      // Invalidate stats
      queryClient.invalidateQueries({
        queryKey: queryKeys.contents.stats(),
      })
      // Invalidate summaries list
      queryClient.invalidateQueries({
        queryKey: queryKeys.summaries.lists(),
      })
      // Clear progress
      setProgress(null)
    },
    onError: () => {
      setIsProcessing(false)
      setProgress(null)
    },
  })

  return {
    ...mutation,
    isProcessing,
    progress,
  }
}
