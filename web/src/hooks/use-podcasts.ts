/**
 * Podcast React Query Hooks
 *
 * Custom hooks for fetching and managing podcasts.
 * Podcasts are audio files generated from approved scripts.
 *
 * @example
 * // Fetch podcasts list
 * const { data } = usePodcasts()
 *
 * @example
 * // Generate audio from script
 * const { mutate } = useGenerateAudio()
 * mutate({ script_id: 1 })
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchPodcasts,
  fetchPodcastStats,
  fetchPodcast,
  generateAudio,
  fetchApprovedScripts,
  type PodcastFilters,
  type GenerateAudioAPIRequest,
} from "@/lib/api/podcasts"

/**
 * Hook to fetch list of podcasts
 *
 * @param filters - Optional filters
 * @returns Query result with podcasts data
 */
export function usePodcasts(filters?: PodcastFilters) {
  return useQuery({
    queryKey: queryKeys.podcasts.list(filters),
    queryFn: () => fetchPodcasts(filters),
  })
}

/**
 * Hook to fetch podcast statistics
 *
 * @returns Query result with statistics
 */
export function usePodcastStats() {
  return useQuery({
    queryKey: queryKeys.podcasts.statistics(),
    queryFn: fetchPodcastStats,
  })
}

/**
 * Hook to fetch a single podcast with full details
 *
 * @param podcastId - Podcast ID
 * @param options - Query options
 * @returns Query result with podcast data
 */
export function usePodcast(podcastId: number, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.podcasts.detail(String(podcastId)),
    queryFn: () => fetchPodcast(podcastId),
    enabled: options?.enabled ?? !!podcastId,
  })
}

/**
 * Hook to fetch approved scripts ready for audio generation
 *
 * @param limit - Maximum results
 * @returns Query result with approved scripts
 */
export function useApprovedScripts(limit: number = 20) {
  return useQuery({
    queryKey: queryKeys.podcasts.approvedScripts(),
    queryFn: () => fetchApprovedScripts(limit),
  })
}

/**
 * Hook to generate audio from an approved script
 *
 * @returns Mutation for audio generation
 */
export function useGenerateAudio() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: GenerateAudioAPIRequest) => generateAudio(request),
    onSuccess: () => {
      // Invalidate podcasts list and statistics
      queryClient.invalidateQueries({
        queryKey: queryKeys.podcasts.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.podcasts.statistics(),
      })
      // Also invalidate scripts as status changes
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.statistics(),
      })
    },
  })
}
