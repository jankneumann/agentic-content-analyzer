/**
 * Job History Types (Task Audit Log)
 *
 * Types for the enriched job history API used by the Task History page.
 * Maps to Python models: JobHistoryItem, JobHistoryResponse.
 */

export interface JobHistoryItem {
  id: number
  entrypoint: string
  task_label: string
  status: "queued" | "in_progress" | "completed" | "failed"
  content_id: number | null
  description: string | null
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface JobHistoryResponse {
  data: JobHistoryItem[]
  pagination: {
    page: number
    page_size: number
    total: number
  }
}

export interface JobHistoryFilters {
  since?: string
  status?: string
  entrypoint?: string
  page?: number
  page_size?: number
}
