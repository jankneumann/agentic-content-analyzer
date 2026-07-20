/**
 * Settings Management Hooks
 *
 * TanStack Query hooks for model configuration, voice settings,
 * and connection status.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchModelSettings,
  updateModelForStep,
  resetModelForStep,
  fetchVoiceSettings,
  updateVoiceSetting,
  resetVoiceSetting,
  fetchConnectionStatus,
} from "@/lib/api/settings"
import {
  fetchSources,
  upsertSource,
  deleteSource,
  setSourceEnabled,
} from "@/lib/api/sources"
import type { SourceUpsertRequest } from "@/types/settings"

// ── Model Configuration ──

export function useModelSettings() {
  return useQuery({
    queryKey: queryKeys.settings.models(),
    queryFn: fetchModelSettings,
  })
}

export function useUpdateModel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ step, modelId }: { step: string; modelId: string }) =>
      updateModelForStep(step, modelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.models() })
    },
  })
}

export function useResetModel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (step: string) => resetModelForStep(step),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.models() })
    },
  })
}

// ── Voice Configuration ──

export function useVoiceSettings() {
  return useQuery({
    queryKey: queryKeys.settings.voice(),
    queryFn: fetchVoiceSettings,
  })
}

export function useUpdateVoice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ field, value }: { field: string; value: string }) =>
      updateVoiceSetting(field, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.voice() })
    },
  })
}

export function useResetVoice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (field: string) => resetVoiceSetting(field),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.voice() })
    },
  })
}

// ── Ingestion Sources ──

export function useSources() {
  return useQuery({
    queryKey: queryKeys.settings.sources(),
    queryFn: fetchSources,
  })
}

export function useUpsertSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: SourceUpsertRequest) => upsertSource(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.sources() })
    },
  })
}

export function useDeleteSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (key: string) => deleteSource(key),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.sources() })
    },
  })
}

export function useSetSourceEnabled() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      setSourceEnabled(key, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.sources() })
    },
  })
}

// ── Connection Status ──

export function useConnectionStatus() {
  return useQuery({
    queryKey: queryKeys.status.connections(),
    queryFn: fetchConnectionStatus,
    refetchInterval: 60000, // refresh every 60s
  })
}
