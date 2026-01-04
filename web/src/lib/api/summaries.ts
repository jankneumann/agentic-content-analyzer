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
  NewsletterSummary,
  SummaryListItem,
  SummarizeRequest,
  SummarizeResponse,
  SummaryFilters,
  PaginatedResponse,
} from "@/types"

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
export async function fetchSummary(id: string): Promise<NewsletterSummary> {
  return apiClient.get<NewsletterSummary>(`/summaries/${id}`)
}

/**
 * Fetch summary by newsletter ID
 *
 * @param newsletterId - Newsletter ID
 * @returns Summary for the newsletter (if exists)
 */
export async function fetchSummaryByNewsletter(
  newsletterId: string
): Promise<NewsletterSummary | null> {
  try {
    return await apiClient.get<NewsletterSummary>(
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
): Promise<SummarizeResponse> {
  return apiClient.post<SummarizeResponse>("/summaries/generate", request)
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
  return apiClient.post<SummarizeResponse>(`/summaries/${summaryId}/regenerate`)
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
  byModel: Record<string, number>
  avgProcessingTime: number
  avgTokenUsage: number
}> {
  return apiClient.get("/summaries/stats")
}
