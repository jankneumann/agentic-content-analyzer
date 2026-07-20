/**
 * Ingestion Sources API Functions
 *
 * API client functions for viewing and managing ingestion source overrides.
 * Sources live under the `/sources` prefix (NOT `/settings`). Read access is
 * public; create / delete / enable-disable require admin authentication, which
 * is handled by the shared apiClient the same way as other admin settings calls.
 */

import { apiClient } from "./client"
import type {
  SourcesOverview,
  SourceUpsertRequest,
  SourceMutationResult,
  SourceDeleteResult,
} from "@/types/settings"

/** Fetch the overview of all configured sources and content counts */
export async function fetchSources(): Promise<SourcesOverview> {
  return apiClient.get<SourcesOverview>("/sources")
}

/** Add or update a source override (upsert by natural key) */
export async function upsertSource(
  request: SourceUpsertRequest
): Promise<SourceMutationResult> {
  return apiClient.post<SourceMutationResult>("/sources", request)
}

/**
 * Delete a source override (DB-origin) or remove a shadow (revert to YAML).
 * The key contains ":" and "/" and must be URL-encoded.
 */
export async function deleteSource(key: string): Promise<SourceDeleteResult> {
  return apiClient.delete<SourceDeleteResult>(
    `/sources/${encodeURIComponent(key)}`
  )
}

/** Enable or disable a source by key (creates a shadow row for YAML sources) */
export async function setSourceEnabled(
  key: string,
  enabled: boolean
): Promise<SourceMutationResult> {
  return apiClient.patch<SourceMutationResult>(
    `/sources/${encodeURIComponent(key)}`,
    { enabled }
  )
}
