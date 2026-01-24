/**
 * Newsletter API Functions
 *
 * API functions for newsletter-related operations.
 * These functions use the apiClient to make requests and
 * are used by React Query hooks for data fetching.
 *
 * @example
 * // Use directly
 * const newsletters = await fetchNewsletters({ status: 'completed' })
 *
 * @example
 * // Use with React Query (preferred)
 * const { data } = useNewsletters({ status: 'completed' })
 */

import { apiClient } from "./client"
import type {
  Newsletter,
  NewsletterListItem,
  NewsletterFilters,
  IngestRequest,
  IngestResponse,
  PaginatedResponse,
  Summary,
} from "@/types"

/**
 * Fetch paginated list of newsletters
 *
 * @param filters - Optional filters for the query
 * @returns Paginated list of newsletters
 */
export async function fetchNewsletters(
  filters?: NewsletterFilters
): Promise<PaginatedResponse<NewsletterListItem>> {
  return apiClient.get<PaginatedResponse<NewsletterListItem>>("/newsletters", {
    params: filters as Record<string, string | number | boolean | undefined>,
  })
}

/**
 * Fetch a single newsletter by ID
 *
 * @param id - Newsletter ID
 * @returns Newsletter with full content
 */
export async function fetchNewsletter(id: string): Promise<Newsletter> {
  return apiClient.get<Newsletter>(`/newsletters/${id}`)
}

/**
 * Fetch newsletter with its summary (if available)
 *
 * @param id - Newsletter ID
 * @returns Newsletter with summary attached
 */
export async function fetchNewsletterWithSummary(
  id: string
): Promise<Newsletter & { summary: Summary | null }> {
  const [newsletter, summary] = await Promise.all([
    fetchNewsletter(id),
    fetchNewsletterSummary(id).catch(() => null),
  ])

  return { ...newsletter, summary }
}

/**
 * Fetch summary for a specific newsletter
 *
 * @param newsletterId - Newsletter ID
 * @returns Newsletter summary
 */
export async function fetchNewsletterSummary(
  newsletterId: string
): Promise<Summary> {
  return apiClient.get<Summary>(`/summaries/by-newsletter/${newsletterId}`)
}

/**
 * Trigger newsletter ingestion
 *
 * Starts the ingestion process from the specified source.
 * Returns immediately with task info - use SSE to track progress.
 *
 * @param request - Ingestion request parameters
 * @returns Ingestion response with counts and IDs
 */
export async function ingestNewsletters(
  request: IngestRequest
): Promise<IngestResponse> {
  return apiClient.post<IngestResponse>("/newsletters/ingest", request)
}

/**
 * Delete a newsletter
 *
 * @param id - Newsletter ID
 */
export async function deleteNewsletter(id: string): Promise<void> {
  return apiClient.delete(`/newsletters/${id}`)
}

/**
 * Get newsletter statistics
 *
 * @returns Statistics about newsletters by status and source
 */
export async function fetchNewsletterStats(): Promise<{
  total: number
  by_status: Record<string, number>
  by_source: Record<string, number>
  pending_count: number
  summarized_count: number
}> {
  return apiClient.get("/newsletters/stats")
}
