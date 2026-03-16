/**
 * Theme Analysis Hooks
 *
 * React Query hooks for theme analysis operations.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  analyzeThemes,
  getAnalysisById,
  getAnalysisStatus,
  getLatestAnalysis,
  listAnalyses,
  type AnalyzeThemesRequest,
} from "@/lib/api/themes"
import { queryKeys } from "@/lib/api/query-keys"

/**
 * Hook to trigger theme analysis
 */
export function useAnalyzeThemes() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: AnalyzeThemesRequest) => analyzeThemes(request),
    onSuccess: () => {
      // Invalidate analyses list to show new analysis
      queryClient.invalidateQueries({ queryKey: queryKeys.themes.all })
    },
  })
}

/**
 * Hook to get analysis status
 */
export function useAnalysisStatus(analysisId: number | null) {
  return useQuery({
    queryKey: queryKeys.themes.analysis(analysisId ?? 0),
    queryFn: () => getAnalysisStatus(analysisId!),
    enabled: analysisId !== null,
    refetchInterval: (query) => {
      // Poll while running
      const status = query.state.data?.status
      if (status === "queued" || status === "running") {
        return 3000 // Poll every 3 seconds
      }
      return false
    },
  })
}

/**
 * Hook to get a single analysis by ID
 */
export function useAnalysisById(id: number | null) {
  return useQuery({
    queryKey: queryKeys.themes.analysis(id ?? 0),
    queryFn: () => getAnalysisById(id!),
    enabled: id !== null,
  })
}

/**
 * Hook to get the latest completed analysis
 */
export function useLatestAnalysis() {
  return useQuery({
    queryKey: queryKeys.themes.latest,
    queryFn: getLatestAnalysis,
  })
}

/**
 * Hook to list recent analyses
 */
export function useAnalysesList(limit: number = 10) {
  return useQuery({
    queryKey: queryKeys.themes.list(limit),
    queryFn: () => listAnalyses(limit),
  })
}
