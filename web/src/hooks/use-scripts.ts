/**
 * Script React Query Hooks
 *
 * Custom hooks for fetching and managing podcast scripts.
 * Scripts are generated from digests and go through a review workflow.
 *
 * @example
 * // Fetch scripts list
 * const { data } = useScripts()
 *
 * @example
 * // Generate new script
 * const { mutate } = useGenerateScript()
 * mutate({ digest_id: 1, length: 'standard' })
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchScripts,
  fetchPendingScripts,
  fetchApprovedScriptsList,
  fetchScriptStats,
  fetchScript,
  fetchScriptNavigation,
  generateScript,
  approveScript,
  rejectScript,
  submitScriptReview,
  reviseScriptSection,
  type ScriptFilters,
} from "@/lib/api/scripts"
import type { GenerateScriptRequest } from "@/types"

/**
 * Hook to fetch list of scripts
 *
 * @param filters - Optional filters
 * @returns Query result with scripts data
 */
export function useScripts(filters?: ScriptFilters) {
  return useQuery({
    queryKey: queryKeys.scripts.list(filters),
    queryFn: () => fetchScripts(filters),
  })
}

/**
 * Hook to fetch scripts pending review
 *
 * @returns Query result with pending scripts
 */
export function usePendingScripts() {
  return useQuery({
    queryKey: queryKeys.scripts.pendingReview(),
    queryFn: fetchPendingScripts,
  })
}

/**
 * Hook to fetch approved scripts (returns ScriptListItem)
 *
 * @returns Query result with approved scripts
 */
export function useApprovedScriptsList() {
  return useQuery({
    queryKey: queryKeys.scripts.approved(),
    queryFn: fetchApprovedScriptsList,
  })
}

/**
 * Hook to fetch script statistics
 *
 * @returns Query result with review statistics
 */
export function useScriptStats() {
  return useQuery({
    queryKey: queryKeys.scripts.statistics(),
    queryFn: fetchScriptStats,
  })
}

/**
 * Hook to fetch a single script with full details
 *
 * @param scriptId - Script ID
 * @param options - Query options
 * @returns Query result with script data
 */
export function useScript(scriptId: number, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.scripts.detail(String(scriptId)),
    queryFn: () => fetchScript(scriptId),
    enabled: options?.enabled ?? !!scriptId,
  })
}

/**
 * Hook to fetch script navigation info
 *
 * @param scriptId - Script ID
 * @returns Query result with navigation data
 */
export function useScriptNavigation(scriptId: number) {
  return useQuery({
    queryKey: [...queryKeys.scripts.detail(String(scriptId)), "navigation"],
    queryFn: () => fetchScriptNavigation(scriptId),
    enabled: !!scriptId,
  })
}

/**
 * Hook to generate a new script
 *
 * @returns Mutation for script generation
 */
export function useGenerateScript() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: GenerateScriptRequest) => generateScript(request),
    onSuccess: () => {
      // Invalidate scripts list
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.statistics(),
      })
    },
  })
}

/**
 * Hook to approve a script
 *
 * @returns Mutation for script approval
 */
export function useApproveScript() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      scriptId,
      reviewer,
      notes,
    }: {
      scriptId: number
      reviewer: string
      notes?: string
    }) => approveScript(scriptId, reviewer, notes),
    onSuccess: (_, { scriptId }) => {
      // Invalidate affected queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.detail(String(scriptId)),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.pendingReview(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.approved(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.statistics(),
      })
    },
  })
}

/**
 * Hook to reject a script
 *
 * @returns Mutation for script rejection
 */
export function useRejectScript() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      scriptId,
      reviewer,
      reason,
    }: {
      scriptId: number
      reviewer: string
      reason: string
    }) => rejectScript(scriptId, reviewer, reason),
    onSuccess: (_, { scriptId }) => {
      // Invalidate affected queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.detail(String(scriptId)),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.pendingReview(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.statistics(),
      })
    },
  })
}

/**
 * Hook to submit a review
 *
 * @returns Mutation for review submission
 */
export function useSubmitScriptReview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      scriptId,
      review,
    }: {
      scriptId: number
      review: {
        action: "approve" | "request_revision" | "reject"
        reviewer: string
        section_feedback?: Record<number, string>
        general_notes?: string
      }
    }) => submitScriptReview(scriptId, review),
    onSuccess: (_, { scriptId }) => {
      // Invalidate affected queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.detail(String(scriptId)),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.pendingReview(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.approved(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.statistics(),
      })
    },
  })
}

/**
 * Hook to revise a script section
 *
 * @returns Mutation for section revision
 */
export function useReviseScriptSection() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      scriptId,
      sectionIndex,
      feedback,
    }: {
      scriptId: number
      sectionIndex: number
      feedback: string
    }) => reviseScriptSection(scriptId, sectionIndex, feedback),
    onSuccess: (_, { scriptId }) => {
      // Invalidate affected queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.detail(String(scriptId)),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scripts.lists(),
      })
    },
  })
}
