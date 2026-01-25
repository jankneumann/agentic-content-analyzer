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
  return apiClient.get<SummaryNavigationInfo>(`/summaries/${summaryId}/navigation`, {
    params: filters as Record<string, string | undefined>,
  })
}

/**
 * Context selection for feedback-based regeneration
 */
export interface ContextSelection {
  text: string
  source: "content" | "summary"
}

/**
 * Request for regenerating a summary with feedback
 */
export interface RegenerateWithFeedbackRequest {
  feedback?: string
  contextSelections?: ContextSelection[]
  previewOnly?: boolean
}

/**
 * Preview data returned from regeneration
 */
export interface SummaryPreviewData {
  executive_summary: string
  key_themes: string[]
  strategic_insights: string[]
  technical_details: string[]
  actionable_items: string[]
  notable_quotes: string[]
  model_used: string
}

/**
 * SSE progress event from regeneration
 */
export interface RegenerationProgressEvent {
  status: "processing" | "completed" | "error"
  message?: string
  progress?: number
  preview?: SummaryPreviewData
}

/**
 * Regenerate a summary with user feedback using SSE streaming
 *
 * @param summaryId - Summary ID to regenerate
 * @param request - Feedback and context selections
 * @param onProgress - Callback for progress updates
 * @returns Promise that resolves with the preview data
 */
export function regenerateSummaryWithFeedback(
  summaryId: string,
  request: RegenerateWithFeedbackRequest,
  onProgress?: (event: RegenerationProgressEvent) => void
): Promise<SummaryPreviewData | null> {
  return new Promise((resolve, reject) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ""

    // Convert request to API format
    const body = {
      feedback: request.feedback,
      context_selections: request.contextSelections?.map((ctx) => ({
        text: ctx.text,
        source: ctx.source,
      })),
      preview_only: request.previewOnly ?? true,
    }

    fetch(`${baseUrl}/api/v1/summaries/${summaryId}/regenerate-with-feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
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
                  const event = JSON.parse(line.slice(6)) as RegenerationProgressEvent
                  onProgress?.(event)

                  if (event.status === "completed" && event.preview) {
                    resolve(event.preview)
                    return
                  }

                  if (event.status === "error") {
                    reject(new Error(event.message || "Regeneration failed"))
                    return
                  }
                } catch {
                  // Skip malformed JSON
                }
              }
            }
          }

          // Stream ended without completion
          resolve(null)
        }

        processStream().catch(reject)
      })
      .catch(reject)
  })
}

/**
 * Request to commit a preview
 */
export interface CommitPreviewRequest {
  executive_summary: string
  key_themes: string[]
  strategic_insights: string[]
  technical_details: string[]
  actionable_items: string[]
  notable_quotes: string[]
}

/**
 * Commit a previewed regeneration, replacing the current summary
 *
 * @param summaryId - Summary ID to update
 * @param preview - Preview data to commit
 * @returns Updated summary
 */
export async function commitSummaryPreview(
  summaryId: string,
  preview: CommitPreviewRequest
): Promise<Summary> {
  return apiClient.post<Summary>(`/summaries/${summaryId}/commit-preview`, preview)
}
