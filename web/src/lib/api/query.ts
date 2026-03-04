/**
 * Content Query API Functions
 *
 * API functions for content query preview operations.
 *
 * @see Backend endpoint: POST /api/v1/contents/query/preview
 */

import { apiClient } from "./client"
import type { ContentQuery, ContentQueryPreview } from "@/types/query"

/**
 * Preview content matching a query
 *
 * Performs a dry-run to show what content would be selected
 * by the given filters, without executing any operation.
 *
 * @param query - Content query filters
 * @returns Preview with counts, breakdowns, and sample titles
 */
export async function previewContentQuery(
  query: ContentQuery
): Promise<ContentQueryPreview> {
  return apiClient.post<ContentQueryPreview>("/contents/query/preview", query)
}
