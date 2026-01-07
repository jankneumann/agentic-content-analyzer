/**
 * Digests API Functions
 *
 * API functions for digest operations.
 * Digests are aggregated reports combining multiple newsletter summaries.
 *
 * @example
 * // Fetch digests list
 * const digests = await fetchDigests()
 *
 * @example
 * // Generate a new digest
 * const result = await generateDigest({ digest_type: 'daily' })
 */

import { apiClient } from "./client"
import type {
  DigestListItem,
  DigestDetail,
  DigestStatistics,
  GenerateDigestRequest,
  DigestReviewRequest,
  DigestFilters,
} from "@/types"

/**
 * Fetch list of digests
 *
 * @param filters - Optional filters
 * @returns List of digests
 */
export async function fetchDigests(
  filters?: DigestFilters
): Promise<DigestListItem[]> {
  return apiClient.get<DigestListItem[]>("/digests/", {
    params: filters as Record<string, string | number | boolean | undefined>,
  })
}

/**
 * Fetch digest statistics
 *
 * @returns Digest statistics
 */
export async function fetchDigestStats(): Promise<DigestStatistics> {
  return apiClient.get<DigestStatistics>("/digests/statistics")
}

/**
 * Fetch a single digest with full details
 *
 * @param digestId - Digest ID
 * @returns Full digest details
 */
export async function fetchDigest(digestId: number): Promise<DigestDetail> {
  return apiClient.get<DigestDetail>(`/digests/${digestId}`)
}

/**
 * Fetch a specific section type from a digest
 *
 * @param digestId - Digest ID
 * @param sectionType - Section type (strategic_insights, technical_developments, emerging_trends)
 * @returns Section details
 */
export async function fetchDigestSection(
  digestId: number,
  sectionType: string
): Promise<{
  digest_id: number
  section_type: string
  sections: Array<{
    title: string
    summary: string
    details: string[]
    themes: string[]
    continuity?: string
  }>
  count: number
}> {
  return apiClient.get(`/digests/${digestId}/sections/${sectionType}`)
}

/**
 * Generate a new digest
 *
 * @param request - Generation request
 * @returns Generation response with status
 */
export async function generateDigest(
  request: GenerateDigestRequest
): Promise<{
  status: string
  message: string
  period_start: string
  period_end: string
}> {
  return apiClient.post("/digests/generate", request)
}

/**
 * Submit a review for a digest
 *
 * @param digestId - Digest ID
 * @param review - Review details
 * @returns Updated digest info
 */
export async function submitDigestReview(
  digestId: number,
  review: DigestReviewRequest
): Promise<{
  digest_id: number
  status: string
  reviewed_by: string
  reviewed_at: string
}> {
  return apiClient.post(`/digests/${digestId}/review`, review)
}

/**
 * Quick approve a digest
 *
 * @param digestId - Digest ID
 * @param reviewer - Reviewer name
 * @param notes - Optional notes
 */
export async function approveDigest(
  digestId: number,
  reviewer: string,
  notes?: string
): Promise<{
  digest_id: number
  status: string
  approved_at: string
}> {
  return apiClient.post(`/digests/${digestId}/approve`, undefined, {
    params: { reviewer, notes },
  })
}

/**
 * Quick reject a digest
 *
 * @param digestId - Digest ID
 * @param reviewer - Reviewer name
 * @param reason - Rejection reason
 */
export async function rejectDigest(
  digestId: number,
  reviewer: string,
  reason: string
): Promise<{
  digest_id: number
  status: string
}> {
  return apiClient.post(`/digests/${digestId}/reject`, undefined, {
    params: { reviewer, reason },
  })
}

/**
 * Revise a specific section of a digest
 *
 * @param digestId - Digest ID
 * @param sectionType - Section type
 * @param sectionIndex - Section index
 * @param feedback - Revision feedback
 */
export async function reviseDigestSection(
  digestId: number,
  sectionType: string,
  sectionIndex: number,
  feedback: string
): Promise<{
  digest_id: number
  section_type: string
  section_index: number
  status: string
  message: string
}> {
  return apiClient.post(
    `/digests/${digestId}/sections/${sectionType}/${sectionIndex}/revise`,
    { feedback }
  )
}

/**
 * Full summary data from digest sources endpoint
 * Includes newsletter metadata for display in review UI
 */
export interface DigestSourceSummary {
  id: number
  newsletter_id: number
  newsletter_title: string
  newsletter_publication: string | null
  executive_summary: string
  key_themes: string[]
  strategic_insights: string[]
  technical_details: string[]
  actionable_items: string[]
  notable_quotes: string[]
  model_used: string
  created_at: string | null
  processing_time_seconds: number | null
}

/**
 * Fetch source summaries for a digest
 *
 * Returns all summaries from newsletters within the digest's period.
 *
 * @param digestId - Digest ID
 * @returns List of source summaries
 */
export async function fetchDigestSources(
  digestId: number
): Promise<DigestSourceSummary[]> {
  return apiClient.get<DigestSourceSummary[]>(`/digests/${digestId}/sources`)
}

/**
 * Navigation info for digest review
 */
export interface DigestNavigationInfo {
  prev_id: number | null
  next_id: number | null
  position: number
  total: number
}

/**
 * Fetch navigation info for prev/next digest
 *
 * @param digestId - Current digest ID
 * @param filters - Optional filters to match list view
 * @returns Navigation info
 */
export async function fetchDigestNavigation(
  digestId: number,
  filters?: DigestFilters
): Promise<DigestNavigationInfo> {
  return apiClient.get<DigestNavigationInfo>(`/digests/${digestId}/navigation`, {
    params: filters as Record<string, string | number | boolean | undefined>,
  })
}
