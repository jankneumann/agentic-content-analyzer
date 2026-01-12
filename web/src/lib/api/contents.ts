/**
 * Content API Functions
 *
 * API functions for the unified Content model operations.
 * These functions use the apiClient to make requests and
 * are used by React Query hooks for data fetching.
 *
 * The Content model unifies newsletters, documents, and other
 * content sources into a single entity.
 *
 * @example
 * // Use directly
 * const contents = await fetchContents({ source_type: 'gmail' })
 *
 * @example
 * // Use with React Query (preferred)
 * const { data } = useContents({ source_type: 'gmail' })
 */

import { apiClient } from "./client"
import type {
  Content,
  ContentListResponse,
  ContentFilters,
  ContentStats,
  ContentCreateRequest,
  ContentDuplicateInfo,
  ContentSource,
  NewsletterSummary,
} from "@/types"

/**
 * Parameters for content ingestion
 */
export interface IngestContentParams {
  source: ContentSource
  max_results?: number
  days_back?: number
  force_reprocess?: boolean
}

/**
 * Response from content ingestion trigger
 */
export interface IngestContentResponse {
  task_id: string
  message: string
  source: ContentSource
  max_results: number
}

/**
 * Fetch paginated list of contents
 *
 * @param filters - Optional filters for the query
 * @returns Paginated list of contents
 */
export async function fetchContents(
  filters?: ContentFilters
): Promise<ContentListResponse> {
  return apiClient.get<ContentListResponse>("/contents", {
    params: filters as Record<string, string | number | boolean | undefined>,
  })
}

/**
 * Fetch a single content by ID
 *
 * @param id - Content ID
 * @returns Content with full markdown content
 */
export async function fetchContent(id: string | number): Promise<Content> {
  return apiClient.get<Content>(`/contents/${id}`)
}

/**
 * Fetch content with its summary (if available)
 *
 * @param id - Content ID
 * @returns Content with summary attached
 */
export async function fetchContentWithSummary(
  id: string | number
): Promise<Content & { summary: NewsletterSummary | null }> {
  const [content, summary] = await Promise.all([
    fetchContent(id),
    fetchContentSummary(id).catch(() => null),
  ])

  return { ...content, summary }
}

/**
 * Fetch summary for a specific content
 *
 * Uses the new /by-content endpoint that queries by content_id directly.
 *
 * @param contentId - Content ID
 * @returns Content summary
 */
export async function fetchContentSummary(
  contentId: string | number
): Promise<NewsletterSummary> {
  return apiClient.get<NewsletterSummary>(`/summaries/by-content/${contentId}`)
}

/**
 * Create new content via API
 *
 * @param request - Content creation request
 * @returns Created content
 */
export async function createContent(
  request: ContentCreateRequest
): Promise<Content> {
  return apiClient.post<Content>("/contents", request)
}

/**
 * Delete content
 *
 * @param id - Content ID
 */
export async function deleteContent(id: string | number): Promise<void> {
  return apiClient.delete(`/contents/${id}`)
}

/**
 * Get content statistics
 *
 * @returns Statistics about content by status and source
 */
export async function fetchContentStats(): Promise<ContentStats> {
  return apiClient.get<ContentStats>("/contents/stats")
}

/**
 * Get duplicates of a content
 *
 * @param id - Content ID
 * @returns List of duplicate contents
 */
export async function fetchContentDuplicates(
  id: string | number
): Promise<Content[]> {
  return apiClient.get<Content[]>(`/contents/${id}/duplicates`)
}

/**
 * Merge a duplicate into the canonical content
 *
 * @param canonicalId - ID of the canonical content
 * @param duplicateId - ID of the duplicate to merge
 * @returns Success message
 */
export async function mergeContentDuplicate(
  canonicalId: string | number,
  duplicateId: string | number
): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(
    `/contents/${canonicalId}/merge/${duplicateId}`
  )
}

/**
 * Trigger content ingestion from a source
 *
 * Starts a background task to ingest content from Gmail, RSS, or YouTube.
 * Returns a task ID for tracking progress.
 *
 * @param params - Ingestion parameters (source, max_results, days_back)
 * @returns Ingestion task response with task_id
 */
export async function ingestContents(
  params: IngestContentParams
): Promise<IngestContentResponse> {
  return apiClient.post<IngestContentResponse>("/contents/ingest", params)
}
