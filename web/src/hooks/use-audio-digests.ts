/**
 * Audio Digest React Query Hooks
 *
 * Custom hooks for fetching and managing audio digests.
 * Audio digests are TTS-generated audio from digests (single-voice narration).
 *
 * @example
 * // Fetch audio digests list
 * const { data } = useAudioDigests()
 *
 * @example
 * // Create audio digest from a digest
 * const { mutate } = useCreateAudioDigest()
 * mutate({ digestId: 1, request: { voice: 'nova', speed: 1.0 } })
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchAudioDigests,
  fetchAudioDigestStats,
  fetchAudioDigest,
  fetchAudioDigestsForDigest,
  createAudioDigest,
  deleteAudioDigest,
  fetchAvailableDigests,
} from "@/lib/api/audio-digests"
import type { AudioDigestFilters, CreateAudioDigestRequest } from "@/types"

/**
 * Hook to fetch list of audio digests
 *
 * @param filters - Optional filters
 * @returns Query result with audio digests data
 */
export function useAudioDigests(filters?: AudioDigestFilters) {
  return useQuery({
    queryKey: queryKeys.audioDigests.list(filters),
    queryFn: () => fetchAudioDigests(filters),
  })
}

/**
 * Hook to fetch audio digest statistics
 *
 * @returns Query result with statistics
 */
export function useAudioDigestStats() {
  return useQuery({
    queryKey: queryKeys.audioDigests.statistics(),
    queryFn: fetchAudioDigestStats,
  })
}

/**
 * Hook to fetch a single audio digest with full details
 *
 * @param audioDigestId - Audio digest ID
 * @param options - Query options
 * @returns Query result with audio digest data
 */
export function useAudioDigest(
  audioDigestId: number,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.audioDigests.detail(String(audioDigestId)),
    queryFn: () => fetchAudioDigest(audioDigestId),
    enabled: options?.enabled ?? !!audioDigestId,
  })
}

/**
 * Hook to fetch audio digests for a specific digest
 *
 * @param digestId - Digest ID
 * @param options - Query options
 * @returns Query result with audio digests for the digest
 */
export function useAudioDigestsForDigest(
  digestId: number,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.audioDigests.byDigest(String(digestId)),
    queryFn: () => fetchAudioDigestsForDigest(digestId),
    enabled: options?.enabled ?? !!digestId,
  })
}

/**
 * Hook to fetch digests available for audio generation
 *
 * @param limit - Maximum results
 * @returns Query result with available digests
 */
export function useAvailableDigests(limit: number = 50) {
  return useQuery({
    queryKey: queryKeys.audioDigests.availableDigests(),
    queryFn: () => fetchAvailableDigests(limit),
  })
}

/**
 * Hook to create an audio digest from a digest
 *
 * @returns Mutation for audio digest creation
 */
export function useCreateAudioDigest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      digestId,
      request,
    }: {
      digestId: number
      request: CreateAudioDigestRequest
    }) => createAudioDigest(digestId, request),
    onSuccess: () => {
      // Invalidate audio digests list and statistics
      queryClient.invalidateQueries({
        queryKey: queryKeys.audioDigests.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.audioDigests.statistics(),
      })
    },
  })
}

/**
 * Hook to delete an audio digest
 *
 * @returns Mutation for audio digest deletion
 */
export function useDeleteAudioDigest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (audioDigestId: number) => deleteAudioDigest(audioDigestId),
    onSuccess: () => {
      // Invalidate audio digests list and statistics
      queryClient.invalidateQueries({
        queryKey: queryKeys.audioDigests.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.audioDigests.statistics(),
      })
    },
  })
}
