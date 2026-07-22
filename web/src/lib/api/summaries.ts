/**
 * Summary API Functions
 *
 * API functions for newsletter summary operations.
 * Summaries are AI-generated extractions of key information
 * from newsletter content.
 *
 * @example
 * // Fetch summaries list
 * const summaries = await fetchSummaries({ limit: 20 })
 *
 * @example
 * // Trigger summarization
 * const result = await triggerSummarization({ newsletterIds: ['id1', 'id2'] })
 */

import { apiClient } from "./client"
import type {
  Summary,
  SummaryListItem,
  SummarizeRequest,
  SummarizeResponse,
  SummaryFilters,
  PaginatedResponse,
} from "@/types"
import type { OperationHandle } from "@/generated/workflow-contracts"

// Re-export for convenience
export type { SummaryFilters }

/**
 * Fetch paginated list of summaries
 *
 * @param filters - Optional filters
 * @returns Paginated list of summaries
 */
export async function fetchSummaries(
  filters?: SummaryFilters
): Promise<PaginatedResponse<SummaryListItem>> {
  return apiClient.get<PaginatedResponse<SummaryListItem>>("/summaries", {
    params: filters as Record<string, string | number | boolean | undefined>,
  })
}

/**
 * Fetch a single summary by ID
 *
 * @param id - Summary ID
 * @returns Full summary details
 */
export async function fetchSummary(id: string): Promise<Summary> {
  return apiClient.get<Summary>(`/summaries/${id}`)
}

/**
 * Fetch summary by newsletter ID
 *
 * @param newsletterId - Newsletter ID
 * @returns Summary for the newsletter (if exists)
 */
export async function fetchSummaryByNewsletter(
  newsletterId: string
): Promise<Summary | null> {
  try {
    return await apiClient.get<Summary>(
      `/summaries/by-newsletter/${newsletterId}`
    )
  } catch (error) {
    // Return null if not found
    if (error instanceof Error && "status" in error && error.status === 404) {
      return null
    }
    throw error
  }
}

/**
 * Trigger summarization for newsletters
 *
 * Starts the summarization process for the specified newsletters.
 * Use SSE to track progress of the task.
 *
 * @param request - Summarization request
 * @returns Response with task ID and queued count
 */
export async function triggerSummarization(
  request: SummarizeRequest
): Promise<OperationHandle> {
  const contentIds = request.content_ids?.length
    ? request.content_ids.map(Number)
    : undefined
  return apiClient.post<OperationHandle>("/summarization-runs", {
    content_ids: contentIds,
    query: contentIds ? undefined : {},
    force_reprocess: request.force,
  })
}

/**
 * Regenerate a summary
 *
 * Forces regeneration of an existing summary.
 *
 * @param summaryId - Summary ID to regenerate
 * @returns New summary response
 */
export async function regenerateSummary(
  summaryId: string
): Promise<SummarizeResponse> {
  throw new Error(
    `Summary regeneration is unavailable after the workflow migration (${summaryId})`
  )
}

/**
 * Delete a summary
 *
 * @param id - Summary ID
 */
export async function deleteSummary(id: string): Promise<void> {
  return apiClient.delete(`/summaries/${id}`)
}

/**
 * Get summary statistics
 *
 * @returns Statistics about summaries
 */
export async function fetchSummaryStats(): Promise<{
  total: number
  by_model: Record<string, number>
  avg_processing_time: number
  avg_token_usage: number
}> {
  return apiClient.get("/summaries/stats")
}

/**
 * Navigation info for prev/next within a filtered list
 */
export interface SummaryNavigationInfo {
  prev_id: number | null
  next_id: number | null
  prev_content_id: number | null
  next_content_id: number | null
  position: number
  total: number
}

/**
 * Filters for navigation query (matches list filters)
 */
export interface SummaryNavigationFilters {
  model_used?: string
  start_date?: string
  end_date?: string
  sort_by?: string
  sort_order?: string
}

/**
 * Get navigation info for a summary
 *
 * Returns prev/next IDs for navigation within a filtered list.
 * Respects the same filters applied on the list view.
 *
 * @param summaryId - Current summary ID
 * @param filters - Optional filters to match list view
 * @returns Navigation info with prev/next IDs
 */
export async function fetchSummaryNavigation(
  summaryId: string,
  filters?: SummaryNavigationFilters
): Promise<SummaryNavigationInfo> {
  return apiClient.get<SummaryNavigationInfo>(
    `/summaries/${summaryId}/navigation`,
    {
      params: filters as Record<string, string | undefined>,
    }
  )
}
