/**
 * Summary React Query Hooks
 *
 * Custom hooks for fetching and managing newsletter summaries.
 * Includes progress tracking for long-running summarization tasks.
 *
 * @example
 * // Fetch summaries list
 * const { data } = useSummaries({ limit: 20 })
 *
 * @example
 * // Trigger summarization with progress
 * const { mutate, isPending } = useTriggerSummarization()
 * mutate({ newsletterIds: ['id1'] })
 */

import { useState, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchSummaries,
  fetchSummary,
  fetchSummaryByNewsletter,
  triggerSummarization,
  regenerateSummary,
  deleteSummary,
  fetchSummaryStats,
  fetchSummaryNavigation,
  type SummaryNavigationFilters,
} from "@/lib/api/summaries"
import { subscribeToProgress, type ProgressEvent } from "@/lib/api/sse"
import type {
  SummarizeRequest,
  SummarizationProgress,
  SummaryFilters,
} from "@/types"

/**
 * Hook to fetch paginated list of summaries
 *
 * @param filters - Optional filters
 * @returns Query result with summaries data
 */
export function useSummaries(filters?: SummaryFilters) {
  return useQuery({
    queryKey: queryKeys.summaries.list(filters),
    queryFn: () => fetchSummaries(filters),
  })
}

/**
 * Hook to fetch a single summary by ID
 *
 * @param id - Summary ID
 * @returns Query result with summary data
 */
export function useSummary(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.summaries.detail(id),
    queryFn: () => fetchSummary(id),
    enabled: options?.enabled ?? !!id,
  })
}

/**
 * Hook to fetch summary by newsletter ID
 *
 * @param newsletterId - Newsletter ID
 * @returns Query result with summary (or null)
 */
export function useSummaryByNewsletter(
  newsletterId: string,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.summaries.byNewsletter(newsletterId),
    queryFn: () => fetchSummaryByNewsletter(newsletterId),
    enabled: options?.enabled ?? !!newsletterId,
  })
}

/**
 * Hook to fetch summary statistics
 */
export function useSummaryStats() {
  return useQuery({
    queryKey: [...queryKeys.summaries.all, "stats"],
    queryFn: fetchSummaryStats,
  })
}

/**
 * Hook to trigger summarization with progress tracking
 *
 * Returns mutation plus progress state for tracking long-running tasks.
 *
 * @example
 * const { mutate, progress, isProcessing } = useTriggerSummarization()
 *
 * mutate({ newsletterIds: ['id1', 'id2'] })
 *
 * // Display progress
 * {isProcessing && <ProgressBar value={progress?.progress || 0} />}
 */
export function useTriggerSummarization() {
  const queryClient = useQueryClient()
  const [progress, setProgress] = useState<SummarizationProgress | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  const mutation = useMutation({
    mutationFn: async (request: SummarizeRequest) => {
      const response = await triggerSummarization(request)

      // Subscribe to progress updates
      if (response.task_id) {
        setIsProcessing(true)

        return new Promise<typeof response>((resolve, reject) => {
          subscribeToProgress<SummarizationProgress>(
            `/summaries/status/${response.task_id}`,
            {
              onProgress: (event: ProgressEvent<SummarizationProgress>) => {
                if (event.data) {
                  setProgress(event.data)
                }
              },
              onComplete: () => {
                setIsProcessing(false)
                setProgress(null)
                resolve(response)
              },
              onError: (error) => {
                setIsProcessing(false)
                setProgress(null)
                reject(error)
              },
            }
          )
        })
      }

      return response
    },
    onSuccess: () => {
      // Invalidate summaries and newsletters lists
      queryClient.invalidateQueries({
        queryKey: queryKeys.summaries.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.newsletters.lists(),
      })
    },
  })

  // Reset progress
  const resetProgress = useCallback(() => {
    setProgress(null)
    setIsProcessing(false)
  }, [])

  return {
    ...mutation,
    progress,
    isProcessing,
    resetProgress,
  }
}

/**
 * Hook to regenerate a summary
 */
export function useRegenerateSummary() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: regenerateSummary,
    onSuccess: (_data, summaryId) => {
      // Invalidate the specific summary
      queryClient.invalidateQueries({
        queryKey: queryKeys.summaries.detail(summaryId),
      })
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: queryKeys.summaries.lists(),
      })
    },
  })
}

/**
 * Hook to delete a summary
 */
export function useDeleteSummary() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteSummary,
    onSuccess: (_data, id) => {
      queryClient.removeQueries({
        queryKey: queryKeys.summaries.detail(id),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.summaries.lists(),
      })
    },
  })
}

/**
 * Hook to fetch navigation info for a summary
 *
 * Returns prev/next IDs for navigating within a filtered list.
 * Respects the same filters applied on the list view.
 *
 * @param summaryId - Current summary ID
 * @param filters - Optional filters to match list view
 * @returns Query result with navigation info
 *
 * @example
 * const { data: nav } = useSummaryNavigation(summaryId, { model_used: 'claude-haiku' })
 * // nav = { prev_id: 1, next_id: 3, position: 2, total: 10 }
 */
export function useSummaryNavigation(
  summaryId: string,
  filters?: SummaryNavigationFilters
) {
  return useQuery({
    queryKey: [...queryKeys.summaries.detail(summaryId), "navigation", filters],
    queryFn: () => fetchSummaryNavigation(summaryId, filters),
    enabled: !!summaryId,
  })
}
