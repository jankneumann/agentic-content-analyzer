/**
 * Task History Page
 *
 * Displays a filterable audit log of all job executions across the pipeline.
 * Shows enriched data: task labels, content descriptions, and timing info.
 *
 * Route: /task-history
 */

import { useState } from "react"
import { createRoute } from "@tanstack/react-router"
import { Loader2 } from "lucide-react"
import { formatDistanceToNow } from "date-fns"

import { Route as rootRoute } from "./__root"
import { PageContainer } from "@/components/layout"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { useJobHistory } from "@/hooks/use-jobs"
import type { JobHistoryFilters } from "@/types"

export const TaskHistoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "task-history",
  component: TaskHistoryPage,
})

/** Maps entrypoint strings to display labels (mirrors Python ENTRYPOINT_LABELS) */
const TASK_TYPE_OPTIONS = [
  { value: "summarize_content", label: "Summarize" },
  { value: "summarize_batch", label: "Summarize (Batch)" },
  { value: "extract_url_content", label: "URL Extraction" },
  { value: "process_content", label: "Process Content" },
  { value: "ingest_content", label: "Ingest" },
]

const STATUS_OPTIONS = [
  { value: "queued", label: "Queued" },
  { value: "in_progress", label: "In Progress" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
]

const TIME_RANGE_OPTIONS = [
  { value: "1d", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "all", label: "All time" },
]

function getStatusBadge(status: string) {
  switch (status) {
    case "completed":
      return <Badge variant="default">Completed</Badge>
    case "failed":
      return <Badge variant="destructive">Failed</Badge>
    case "in_progress":
      return <Badge variant="secondary">In Progress</Badge>
    case "queued":
      return <Badge variant="outline">Queued</Badge>
    default:
      return <Badge variant="outline">{status}</Badge>
  }
}

function TaskHistoryPage() {
  const [filters, setFilters] = useState<JobHistoryFilters>({
    page: 1,
    page_size: 50,
  })

  const { data, isLoading } = useJobHistory(filters)

  const updateFilter = (key: keyof JobHistoryFilters, value: string | undefined) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
      page: 1, // Reset page when filters change
    }))
  }

  const totalPages = data ? Math.ceil(data.pagination.total / data.pagination.page_size) : 0

  return (
    <PageContainer
      title="Task History"
      description="Audit log of all pipeline task executions"
    >
      {/* Filter Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <Select
          value={filters.since ?? "all"}
          onValueChange={(v) => updateFilter("since", v === "all" ? undefined : v)}
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Time range" />
          </SelectTrigger>
          <SelectContent>
            {TIME_RANGE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filters.entrypoint ?? "all"}
          onValueChange={(v) => updateFilter("entrypoint", v === "all" ? undefined : v)}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Task type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All task types</SelectItem>
            {TASK_TYPE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filters.status ?? "all"}
          onValueChange={(v) => updateFilter("status", v === "all" ? undefined : v)}
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : !data || data.data.length === 0 ? (
        <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
          <p className="text-sm text-muted-foreground">
            No task history found
          </p>
        </div>
      ) : (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date/Time</TableHead>
                  <TableHead>Task</TableHead>
                  <TableHead className="hidden md:table-cell">Content ID</TableHead>
                  <TableHead className="hidden md:table-cell">Job ID</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.data.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {formatDistanceToNow(new Date(item.created_at), {
                        addSuffix: true,
                      })}
                    </TableCell>
                    <TableCell className="font-medium">
                      {item.task_label}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-muted-foreground">
                      {item.content_id ?? "-"}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-muted-foreground">
                      {item.id}
                    </TableCell>
                    <TableCell className="max-w-[300px] truncate">
                      {item.description ?? (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>{getStatusBadge(item.status)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-muted-foreground">
                Page {data.pagination.page} of {totalPages} ({data.pagination.total} total)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={data.pagination.page <= 1}
                  onClick={() =>
                    setFilters((prev) => ({
                      ...prev,
                      page: (prev.page ?? 1) - 1,
                    }))
                  }
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={data.pagination.page >= totalPages}
                  onClick={() =>
                    setFilters((prev) => ({
                      ...prev,
                      page: (prev.page ?? 1) + 1,
                    }))
                  }
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </PageContainer>
  )
}
