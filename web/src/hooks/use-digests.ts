/**
 * Digest React Query Hooks
 *
 * Custom hooks for fetching and managing digests.
 * Digests are aggregated reports combining newsletter summaries.
 *
 * @example
 * // Fetch digests list
 * const { data } = useDigests()
 *
 * @example
 * // Generate new digest
 * const { mutate } = useGenerateDigest()
 * mutate({ digest_type: 'daily' })
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchDigests,
  fetchDigestStats,
  fetchDigest,
  fetchDigestSection,
  generateDigest,
  submitDigestReview,
  approveDigest,
  rejectDigest,
  reviseDigestSection,
} from "@/lib/api/digests"
import type {
  DigestFilters,
  GenerateDigestRequest,
  DigestReviewRequest,
} from "@/types"

/**
 * Hook to fetch list of digests
 *
 * @param filters - Optional filters
 * @returns Query result with digests data
 */
export function useDigests(filters?: DigestFilters) {
  return useQuery({
    queryKey: queryKeys.digests.list(filters),
    queryFn: () => fetchDigests(filters),
  })
}

/**
 * Hook to fetch digest statistics
 *
 * @returns Query result with statistics
 */
export function useDigestStats() {
  return useQuery({
    queryKey: queryKeys.digests.statistics(),
    queryFn: fetchDigestStats,
  })
}

/**
 * Hook to fetch a single digest with full details
 *
 * @param digestId - Digest ID
 * @param options - Query options
 * @returns Query result with digest data
 */
export function useDigest(digestId: number, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.digests.detail(String(digestId)),
    queryFn: () => fetchDigest(digestId),
    enabled: options?.enabled ?? !!digestId,
  })
}

/**
 * Hook to fetch a specific section of a digest
 *
 * @param digestId - Digest ID
 * @param sectionType - Section type
 * @param options - Query options
 * @returns Query result with section data
 */
export function useDigestSection(
  digestId: number,
  sectionType: string,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: [...queryKeys.digests.detail(String(digestId)), "section", sectionType],
    queryFn: () => fetchDigestSection(digestId, sectionType),
    enabled: options?.enabled ?? (!!digestId && !!sectionType),
  })
}

/**
 * Hook to generate a new digest
 *
 * @returns Mutation for digest generation
 */
export function useGenerateDigest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: GenerateDigestRequest) => generateDigest(request),
    onSuccess: () => {
      // Invalidate digests list
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.statistics(),
      })
    },
  })
}

/**
 * Hook to submit a digest review
 *
 * @returns Mutation for review submission
 */
export function useSubmitDigestReview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      digestId,
      review,
    }: {
      digestId: number
      review: DigestReviewRequest
    }) => submitDigestReview(digestId, review),
    onSuccess: (_, { digestId }) => {
      // Invalidate affected queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.detail(String(digestId)),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.statistics(),
      })
    },
  })
}

/**
 * Hook to approve a digest
 *
 * @returns Mutation for digest approval
 */
export function useApproveDigest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      digestId,
      reviewer,
      notes,
    }: {
      digestId: number
      reviewer: string
      notes?: string
    }) => approveDigest(digestId, reviewer, notes),
    onSuccess: (_, { digestId }) => {
      // Invalidate affected queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.detail(String(digestId)),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.pendingReview(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.statistics(),
      })
    },
  })
}

/**
 * Hook to reject a digest
 *
 * @returns Mutation for digest rejection
 */
export function useRejectDigest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      digestId,
      reviewer,
      reason,
    }: {
      digestId: number
      reviewer: string
      reason: string
    }) => rejectDigest(digestId, reviewer, reason),
    onSuccess: (_, { digestId }) => {
      // Invalidate affected queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.detail(String(digestId)),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.statistics(),
      })
    },
  })
}

/**
 * Hook to revise a digest section
 *
 * @returns Mutation for section revision
 */
export function useReviseDigestSection() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      digestId,
      sectionType,
      sectionIndex,
      feedback,
    }: {
      digestId: number
      sectionType: string
      sectionIndex: number
      feedback: string
    }) => reviseDigestSection(digestId, sectionType, sectionIndex, feedback),
    onSuccess: (_, { digestId }) => {
      // Invalidate affected queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.detail(String(digestId)),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.digests.lists(),
      })
    },
  })
}
