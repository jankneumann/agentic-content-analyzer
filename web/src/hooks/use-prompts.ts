/**
 * Prompt Management Hooks
 *
 * TanStack Query hooks for fetching and managing LLM prompts.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchPrompts,
  fetchPrompt,
  updatePrompt,
  resetPrompt,
  testPrompt,
} from "@/lib/api/prompts"
import type {
  PromptUpdateRequest,
  PromptTestRequest,
} from "@/types/prompt"

/**
 * Hook to fetch all prompts
 */
export function usePrompts() {
  return useQuery({
    queryKey: queryKeys.prompts.lists(),
    queryFn: fetchPrompts,
  })
}

/**
 * Hook to fetch a single prompt by key
 */
export function usePrompt(key: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.prompts.detail(key),
    queryFn: () => fetchPrompt(key),
    enabled: options?.enabled ?? !!key,
  })
}

/**
 * Hook to update a prompt override
 */
export function useUpdatePrompt() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ key, data }: { key: string; data: PromptUpdateRequest }) =>
      updatePrompt(key, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.prompts.all })
    },
  })
}

/**
 * Hook to reset a prompt override to default
 */
export function useResetPrompt() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (key: string) => resetPrompt(key),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.prompts.all })
    },
  })
}

/**
 * Hook to test a prompt template
 */
export function useTestPrompt() {
  return useMutation({
    mutationFn: ({ key, data }: { key: string; data: PromptTestRequest }) =>
      testPrompt(key, data),
  })
}
