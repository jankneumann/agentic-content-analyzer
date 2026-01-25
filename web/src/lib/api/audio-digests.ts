/**
 * Audio Digests API Functions
 *
 * API functions for audio digest operations.
 * Audio digests are TTS-generated audio from digests (single-voice narration).
 *
 * @example
 * // Fetch audio digests list
 * const audioDigests = await fetchAudioDigests()
 *
 * @example
 * // Create audio digest from a digest
 * const result = await createAudioDigest(digestId, { voice: 'nova', speed: 1.0 })
 */

import { apiClient } from "./client"
import type {
  AudioDigestListItem,
  AudioDigestDetail,
  AudioDigestStatistics,
  AudioDigestFilters,
  CreateAudioDigestRequest,
  CreateAudioDigestResponse,
  AvailableDigest,
} from "@/types"

/**
 * Fetch list of audio digests
 *
 * @param filters - Optional filters
 * @returns List of audio digests
 */
export async function fetchAudioDigests(
  filters?: AudioDigestFilters
): Promise<AudioDigestListItem[]> {
  return apiClient.get<AudioDigestListItem[]>("/audio-digests/", {
    params: filters as Record<string, string | number | boolean | undefined>,
  })
}

/**
 * Fetch audio digest statistics
 *
 * @returns Audio digest statistics
 */
export async function fetchAudioDigestStats(): Promise<AudioDigestStatistics> {
  return apiClient.get<AudioDigestStatistics>("/audio-digests/statistics")
}

/**
 * Fetch a single audio digest with full details
 *
 * @param audioDigestId - Audio digest ID
 * @returns Full audio digest details
 */
export async function fetchAudioDigest(
  audioDigestId: number
): Promise<AudioDigestDetail> {
  return apiClient.get<AudioDigestDetail>(`/audio-digests/${audioDigestId}`)
}

/**
 * Fetch audio digests for a specific digest
 *
 * @param digestId - Digest ID
 * @returns List of audio digests for the digest
 */
export async function fetchAudioDigestsForDigest(
  digestId: number
): Promise<AudioDigestListItem[]> {
  return apiClient.get<AudioDigestListItem[]>(`/digests/${digestId}/audio`)
}

/**
 * Create an audio digest from a digest
 *
 * Triggers background audio generation.
 *
 * @param digestId - Source digest ID
 * @param request - Generation configuration
 * @returns Creation response with audio digest ID
 */
export async function createAudioDigest(
  digestId: number,
  request: CreateAudioDigestRequest
): Promise<CreateAudioDigestResponse> {
  return apiClient.post(`/digests/${digestId}/audio`, request)
}

/**
 * Delete an audio digest
 *
 * @param audioDigestId - Audio digest ID to delete
 */
export async function deleteAudioDigest(audioDigestId: number): Promise<void> {
  return apiClient.delete(`/audio-digests/${audioDigestId}`)
}

/**
 * Get audio stream URL for an audio digest
 *
 * @param audioDigestId - Audio digest ID
 * @returns Audio stream URL
 */
export function getAudioDigestUrl(audioDigestId: number): string {
  return `/api/v1/audio-digests/${audioDigestId}/stream`
}

/**
 * Fetch digests available for audio generation
 *
 * Returns completed/approved digests that can be converted to audio.
 *
 * @param limit - Maximum results
 * @returns List of available digests
 */
export async function fetchAvailableDigests(
  limit: number = 50
): Promise<AvailableDigest[]> {
  return apiClient.get<AvailableDigest[]>("/digests/", {
    params: {
      status: "approved,completed",
      limit,
      sort_by: "created_at",
      sort_order: "desc",
    },
  })
}
