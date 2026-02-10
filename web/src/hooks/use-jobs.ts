/**
 * Job History React Query Hooks
 *
 * Custom hook for fetching enriched job history data
 * from GET /api/v1/jobs/history.
 */

import { useQuery } from "@tanstack/react-query"
import type { JobHistoryResponse, JobHistoryFilters } from "@/types"

const API_BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, "") ?? ""

export const jobHistoryKeys = {
  all: ["job-history"] as const,
  list: (filters?: JobHistoryFilters) =>
    [...jobHistoryKeys.all, "list", filters] as const,
}

async function fetchJobHistory(
  filters: JobHistoryFilters = {}
): Promise<JobHistoryResponse> {
  const params = new URLSearchParams()
  if (filters.since) params.set("since", filters.since)
  if (filters.status) params.set("status", filters.status)
  if (filters.entrypoint) params.set("entrypoint", filters.entrypoint)
  if (filters.page) params.set("page", String(filters.page))
  if (filters.page_size) params.set("page_size", String(filters.page_size))

  const url = `${API_BASE}/api/v1/jobs/history?${params.toString()}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to fetch job history: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Hook to fetch paginated job history with filters
 */
export function useJobHistory(filters: JobHistoryFilters = {}) {
  return useQuery({
    queryKey: jobHistoryKeys.list(filters),
    queryFn: () => fetchJobHistory(filters),
    placeholderData: (previousData) => previousData,
  })
}
