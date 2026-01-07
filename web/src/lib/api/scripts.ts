/**
 * Scripts API Functions
 *
 * API functions for podcast script operations.
 * Scripts are generated from digests and go through a review workflow.
 *
 * @example
 * // Fetch scripts list
 * const scripts = await fetchScripts()
 *
 * @example
 * // Generate a new script
 * const result = await generateScript({ digest_id: 1 })
 */

import { apiClient } from "./client"
import type {
  ScriptListItem,
  ScriptReviewStatistics,
  GenerateScriptRequest,
  GenerateScriptResponse,
} from "@/types"
import type { ScriptDetail } from "@/types/review"

/**
 * Script filters for list queries
 */
export interface ScriptFilters {
  /** Filter by status */
  status?: string
  /** Filter by digest ID */
  digest_id?: number
  /** Maximum results */
  limit?: number
}

/**
 * Fetch list of scripts
 *
 * @param filters - Optional filters
 * @returns List of scripts
 */
export async function fetchScripts(
  filters?: ScriptFilters
): Promise<ScriptListItem[]> {
  return apiClient.get<ScriptListItem[]>("/scripts/", {
    params: filters as Record<string, string | number | boolean | undefined>,
  })
}

/**
 * Fetch scripts pending review
 *
 * @returns List of scripts pending review
 */
export async function fetchPendingScripts(): Promise<ScriptListItem[]> {
  return apiClient.get<ScriptListItem[]>("/scripts/pending-review")
}

/**
 * Fetch approved scripts ready for audio (returns ScriptListItem)
 *
 * @returns List of approved scripts
 */
export async function fetchApprovedScriptsList(): Promise<ScriptListItem[]> {
  return apiClient.get<ScriptListItem[]>("/scripts/approved")
}

/**
 * Fetch scripts for a specific digest
 *
 * @param digestId - Digest ID
 * @returns List of scripts for the digest
 */
export async function fetchScriptsForDigest(
  digestId: number
): Promise<ScriptListItem[]> {
  return apiClient.get<ScriptListItem[]>(`/scripts/digest/${digestId}`)
}

/**
 * Fetch script review statistics
 *
 * @returns Review workflow statistics
 */
export async function fetchScriptStats(): Promise<ScriptReviewStatistics> {
  return apiClient.get<ScriptReviewStatistics>("/scripts/statistics")
}

/**
 * Fetch a single script with full details
 *
 * @param scriptId - Script ID
 * @returns Full script details for review
 */
export async function fetchScript(scriptId: number): Promise<ScriptDetail> {
  return apiClient.get<ScriptDetail>(`/scripts/${scriptId}`)
}

/**
 * Fetch navigation info for a script
 *
 * @param scriptId - Script ID
 * @returns Navigation info (prev/next IDs, position, total)
 */
export async function fetchScriptNavigation(scriptId: number): Promise<{
  prev_id: number | null
  next_id: number | null
  position: number
  total: number
}> {
  return apiClient.get(`/scripts/${scriptId}/navigation`)
}

/**
 * Fetch a specific section of a script
 *
 * @param scriptId - Script ID
 * @param sectionIndex - Section index
 * @returns Section details
 */
export async function fetchScriptSection(
  scriptId: number,
  sectionIndex: number
): Promise<Record<string, unknown>> {
  return apiClient.get<Record<string, unknown>>(
    `/scripts/${scriptId}/sections/${sectionIndex}`
  )
}

/**
 * Generate a new podcast script from a digest
 *
 * @param request - Generation request
 * @returns Generation response with status
 */
export async function generateScript(
  request: GenerateScriptRequest
): Promise<GenerateScriptResponse> {
  return apiClient.post<GenerateScriptResponse>("/scripts/generate", request)
}

/**
 * Submit a review for a script
 *
 * @param scriptId - Script ID
 * @param review - Review details
 * @returns Updated script info
 */
export async function submitScriptReview(
  scriptId: number,
  review: {
    action: "approve" | "request_revision" | "reject"
    reviewer: string
    section_feedback?: Record<number, string>
    general_notes?: string
  }
): Promise<{
  script_id: number
  status: string
  revision_count: number
  reviewed_by: string | null
  reviewed_at: string | null
}> {
  return apiClient.post(`/scripts/${scriptId}/review`, review)
}

/**
 * Quick approve a script
 *
 * @param scriptId - Script ID
 * @param reviewer - Reviewer name
 * @param notes - Optional notes
 */
export async function approveScript(
  scriptId: number,
  reviewer: string,
  notes?: string
): Promise<{
  script_id: number
  status: string
  approved_at: string | null
}> {
  return apiClient.post(`/scripts/${scriptId}/approve`, undefined, {
    params: { reviewer, notes },
  })
}

/**
 * Quick reject a script
 *
 * @param scriptId - Script ID
 * @param reviewer - Reviewer name
 * @param reason - Rejection reason
 */
export async function rejectScript(
  scriptId: number,
  reviewer: string,
  reason: string
): Promise<{
  script_id: number
  status: string
}> {
  return apiClient.post(`/scripts/${scriptId}/reject`, undefined, {
    params: { reviewer, reason },
  })
}

/**
 * Revise a specific section of a script
 *
 * @param scriptId - Script ID
 * @param sectionIndex - Section to revise
 * @param feedback - Revision feedback
 */
export async function reviseScriptSection(
  scriptId: number,
  sectionIndex: number,
  feedback: string
): Promise<{
  script_id: number
  section_revised: number
  status: string
  revision_count: number
}> {
  return apiClient.post(`/scripts/${scriptId}/sections/${sectionIndex}/revise`, {
    feedback,
  })
}
