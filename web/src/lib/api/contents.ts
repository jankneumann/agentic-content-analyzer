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
  Summary,
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
): Promise<Content & { summary: Summary | null }> {
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
): Promise<Summary> {
  return apiClient.get<Summary>(`/summaries/by-content/${contentId}`)
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

// ============================================================================
// Content Summarization API
// ============================================================================

/**
 * Parameters for content summarization
 */
export interface SummarizeContentParams {
  /** Specific content IDs to summarize (empty = all pending) */
  content_ids?: number[]
  /** Force re-summarization even if summary exists */
  force?: boolean
  /** Include failed content items (reset to PARSED and retry) */
  retry_failed?: boolean
}

/**
 * Response from content summarization trigger
 */
export interface SummarizeContentResponse {
  task_id: string
  message: string
  queued_count: number
  content_ids: number[]
}

/**
 * SSE progress event from content summarization
 */
export interface ContentSummarizationProgressEvent {
  status: "queued" | "processing" | "completed" | "error"
  progress: number
  total: number
  processed: number
  completed: number
  failed: number
  current_content_id: number | null
  message: string
  started_at: string
}

/**
 * Trigger summarization for content records
 *
 * If content_ids is empty, summarizes all pending/parsed content.
 * Returns a task ID for tracking progress via SSE.
 *
 * @param params - Summarization parameters
 * @returns Summarization task response with task_id
 */
export async function summarizeContents(
  params: SummarizeContentParams = {}
): Promise<SummarizeContentResponse> {
  return apiClient.post<SummarizeContentResponse>("/contents/summarize", params)
}

/**
 * Track content summarization progress via SSE
 *
 * @param taskId - Task ID from summarizeContents response
 * @param onProgress - Callback for progress updates
 * @returns Promise that resolves when summarization completes
 */
export function trackContentSummarization(
  taskId: string,
  onProgress?: (event: ContentSummarizationProgressEvent) => void
): Promise<ContentSummarizationProgressEvent> {
  return new Promise((resolve, reject) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ""

    fetch(`${baseUrl}/api/v1/contents/summarize/status/${taskId}`, {
      headers: {
        Accept: "text/event-stream",
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error("No response body")
        }

        const decoder = new TextDecoder()
        let buffer = ""

        const processStream = async () => {
          while (true) {
            const { done, value } = await reader.read()

            if (done) break

            buffer += decoder.decode(value, { stream: true })

            // Process complete SSE messages
            const lines = buffer.split("\n")
            buffer = lines.pop() || "" // Keep incomplete line in buffer

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const event = JSON.parse(
                    line.slice(6)
                  ) as ContentSummarizationProgressEvent
                  onProgress?.(event)

                  if (event.status === "completed" || event.status === "error") {
                    resolve(event)
                    return
                  }
                } catch {
                  // Skip malformed JSON
                }
              }
            }
          }

          // Stream ended without completion event
          reject(new Error("Stream ended unexpectedly"))
        }

        processStream().catch(reject)
      })
      .catch(reject)
  })
}
