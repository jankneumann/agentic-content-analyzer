/**
 * Podcasts API Functions
 *
 * API functions for podcast audio operations.
 * Podcasts are generated from approved scripts using TTS.
 *
 * @example
 * // Fetch podcasts list
 * const podcasts = await fetchPodcasts()
 *
 * @example
 * // Generate audio from script
 * const result = await generateAudio({ script_id: 1 })
 */

import { apiClient } from "./client"
import type {
  PodcastListItem,
  PodcastDetail,
  PodcastStatistics,
  ApprovedScript,
} from "@/types"

/**
 * Podcast filters for list queries
 */
export interface PodcastFilters {
  /** Filter by status */
  status?: string
  /** Maximum results */
  limit?: number
  /** Pagination offset */
  offset?: number
}

/**
 * Request to generate audio
 */
export interface GenerateAudioAPIRequest {
  script_id: number
  voice_provider?: string
  alex_voice?: string
  sam_voice?: string
}

/**
 * Fetch list of podcasts
 *
 * @param filters - Optional filters
 * @returns List of podcasts
 */
export async function fetchPodcasts(
  filters?: PodcastFilters
): Promise<PodcastListItem[]> {
  return apiClient.get<PodcastListItem[]>("/podcasts/", {
    params: filters as Record<string, string | number | boolean | undefined>,
  })
}

/**
 * Fetch podcast statistics
 *
 * @returns Podcast statistics
 */
export async function fetchPodcastStats(): Promise<PodcastStatistics> {
  return apiClient.get<PodcastStatistics>("/podcasts/statistics")
}

/**
 * Fetch a single podcast with full details
 *
 * @param podcastId - Podcast ID
 * @returns Full podcast details
 */
export async function fetchPodcast(podcastId: number): Promise<PodcastDetail> {
  return apiClient.get<PodcastDetail>(`/podcasts/${podcastId}`)
}

/**
 * Generate audio from an approved script
 *
 * @param request - Generation request
 * @returns Generation response with podcast ID
 */
export async function generateAudio(
  request: GenerateAudioAPIRequest
): Promise<{
  status: string
  message: string
  podcast_id: number
  script_id: number
}> {
  return apiClient.post("/podcasts/generate", request)
}

/**
 * Get audio stream URL for a podcast
 *
 * @param podcastId - Podcast ID
 * @returns Audio stream URL
 */
export function getAudioUrl(podcastId: number): string {
  return `/api/v1/podcasts/${podcastId}/audio`
}

/**
 * Fetch approved scripts ready for audio generation
 *
 * @param limit - Maximum results
 * @returns List of approved scripts
 */
export async function fetchApprovedScripts(
  limit: number = 20
): Promise<ApprovedScript[]> {
  return apiClient.get<ApprovedScript[]>("/podcasts/approved-scripts", {
    params: { limit },
  })
}
