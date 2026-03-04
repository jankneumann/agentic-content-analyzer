/**
 * Summaries Page
 *
 * Displays AI-generated summaries of newsletters.
 * Allows viewing summary details and triggering summarization.
 *
 * Route: /summaries
 */

import { useState } from "react"
import { createRoute, Link } from "@tanstack/react-router"
import {
  Sparkles,
  Play,
  RefreshCw,
  Search,
  Clock,
  Zap,
  Eye,
  AlertCircle,
  Loader2,
  FileSearch,
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"

import { Route as rootRoute } from "./__root"
import { PageContainer } from "@/components/layout"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  SortableTableHead,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  useSummaries,
  useSummary,
  useSummaryStats,
  useContentStats,
  useSummarizeContents,
} from "@/hooks"
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext"
import {
  GenerateSummaryDialog,
  type SummaryGenerationParams,
} from "@/components/generation"
import type { SummaryFilters, SummaryListItem } from "@/types"

export const SummariesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "summaries",
  component: SummariesPage,
})

function SummariesPage() {
  const [filters, setFilters] = useState<SummaryFilters>({
    limit: 20,
    offset: 0,
  })
  const [searchValue, setSearchValue] = useState("")
  const [selectedSummaryId, setSelectedSummaryId] = useState<string | null>(null)
  const [showGenerateDialog, setShowGenerateDialog] = useState(false)

  const { data, isLoading, isError, error, refetch } = useSummaries(filters)
  const { data: stats } = useSummaryStats()
  const { data: contentStats } = useContentStats()
  const summarizeMutation = useSummarizeContents()
  const { addTask, updateTask, completeTask, failTask } = useBackgroundTasks()

  // Content items that need summarization (don't have summaries yet)
  const pendingCount = contentStats?.needs_summarization_count ?? 0
  // Failed content items that could be retried
  const failedCount = contentStats?.failed_count ?? 0

  // Fetch selected summary details
  const { data: selectedSummary, isLoading: isLoadingSummary } = useSummary(
    selectedSummaryId ?? "",
    { enabled: !!selectedSummaryId }
  )

  const handleSearch = (value: string) => {
    setSearchValue(value)
    // Note: Backend would need to support search filter
  }

  const handleModelFilter = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      model_used: value === "all" ? undefined : value,
      offset: 0,
    }))
  }

  const handleSort = (column: string, order: "asc" | "desc" | undefined) => {
    setFilters((prev) => ({
      ...prev,
      sort_by: order ? column : undefined,
      sort_order: order,
      offset: 0, // Reset to first page when sort changes
    }))
  }

  const handleGenerateSummaries = (params: SummaryGenerationParams) => {
    // Close dialog immediately - task runs in background
    setShowGenerateDialog(false)

    // Convert newsletter_ids to content_ids for the new API
    // The dialog still uses newsletter_ids for now, but we pass empty array
    // to summarize all pending content
    const contentIds = params.newsletter_ids.length > 0 ? params.newsletter_ids : []
    const count = contentIds.length || (pendingCount + (params.retry_failed ? failedCount : 0))

    // Add background task
    const taskId = addTask({
      type: "summary",
      title: `Summarize ${count} content item${count !== 1 ? "s" : ""}`,
      message: "Starting summarization...",
    })

    // Track progress from SSE via mutation's progress state
    let lastProgress = 0
    const progressInterval = setInterval(() => {
      if (summarizeMutation.progress) {
        const p = summarizeMutation.progress
        if (p.progress !== lastProgress) {
          lastProgress = p.progress
          updateTask(taskId, {
            progress: p.progress,
            message: p.message || `Processing ${p.processed || 0}/${p.total || count}...`
          })
        }
      }
    }, 500)

    summarizeMutation.mutate(
      {
        content_ids: contentIds,
        query: params.content_query,
        force: params.force,
        retry_failed: params.retry_failed,
      },
      {
        onSuccess: (result) => {
          clearInterval(progressInterval)
          const completed = result?.completed ?? count
          completeTask(taskId, `Summarization complete: ${completed} summaries created`)
          toast.success(`Summarized ${completed} content items`)
          refetch()
        },
        onError: (err) => {
          clearInterval(progressInterval)
          const errorMsg = err instanceof Error ? err.message : "Unknown error"
          failTask(taskId, errorMsg)
          toast.error(`Failed to summarize: ${errorMsg}`)
        },
      }
    )

    // Update progress indicator
    updateTask(taskId, { progress: 5, message: "Queuing summarization..." })
  }

  return (
    <PageContainer
      title="Summaries"
      description="AI-generated newsletter summaries with key themes and insights"
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button onClick={() => setShowGenerateDialog(true)}>
            <Play className="mr-2 h-4 w-4" />
            Generate Summaries
          </Button>
        </div>
      }
    >
      {/* Progress indicator */}
      {summarizeMutation.isProcessing && summarizeMutation.progress && (
        <Card className="border-primary/50 bg-primary/5">
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <div className="flex-1">
                <p className="text-sm font-medium">
                  Summarizing content... ({summarizeMutation.progress.progress}%)
                </p>
                <p className="text-xs text-muted-foreground">
                  {summarizeMutation.progress.message}
                </p>
              </div>
              <Badge variant="outline">
                {summarizeMutation.progress.processed ?? 0} / {summarizeMutation.progress.total ?? 0}
              </Badge>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Summaries</CardDescription>
              <CardTitle className="text-2xl">{stats.total}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Avg Processing</CardDescription>
              <CardTitle className="text-2xl">
                {stats.avg_processing_time?.toFixed(1) ?? "0"}s
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Avg Tokens</CardDescription>
              <CardTitle className="text-2xl">
                {Math.round(stats.avg_token_usage ?? 0).toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Models Used</CardDescription>
              <CardTitle className="text-2xl">
                {Object.keys(stats.by_model ?? {}).length}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Summary list */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Summary List</CardTitle>
          </div>
          <CardDescription>
            {data?.total ?? 0} summaries generated
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filter row */}
          <div className="mb-4 flex flex-col gap-4 md:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search summaries..."
                value={searchValue}
                onChange={(e) => handleSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={filters.model_used ?? "all"}
              onValueChange={handleModelFilter}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Model" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Models</SelectItem>
                {stats?.by_model &&
                  Object.keys(stats.by_model).map((model) => (
                    <SelectItem key={model} value={model}>
                      {model}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
              <div className="text-center">
                <AlertCircle className="mx-auto h-12 w-12 text-destructive/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  Error loading summaries: {error?.message}
                </p>
                <Button className="mt-4" size="sm" onClick={() => refetch()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Retry
                </Button>
              </div>
            </div>
          ) : data?.items.length === 0 ? (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
              <div className="text-center">
                <Sparkles className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  No summaries generated yet
                </p>
                <p className="text-xs text-muted-foreground">
                  Ingest content first, then generate summaries
                </p>
                <Button
                  className="mt-4"
                  size="sm"
                  onClick={() => setShowGenerateDialog(true)}
                >
                  <Play className="mr-2 h-4 w-4" />
                  Generate Summaries
                </Button>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableTableHead
                    column="title"
                    label="Content"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                  />
                  <TableHead className="w-[200px]">Key Themes</TableHead>
                  <SortableTableHead
                    column="model_used"
                    label="Model"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[120px]"
                  />
                  <SortableTableHead
                    column="processing_time_seconds"
                    label="Time"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[100px]"
                  />
                  <SortableTableHead
                    column="created_at"
                    label="Created"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[130px]"
                  />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((summary) => (
                  <SummaryRow
                    key={summary.id}
                    summary={summary}
                    onView={() => setSelectedSummaryId(String(summary.id))}
                  />
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {data && data.total > data.limit && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Showing {data.offset + 1} to{" "}
                {Math.min(data.offset + data.limit, data.total)} of {data.total}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={data.offset === 0}
                  onClick={() =>
                    setFilters((prev) => ({
                      ...prev,
                      offset: Math.max(0, (prev.offset ?? 0) - (prev.limit ?? 20)),
                    }))
                  }
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!data.has_more}
                  onClick={() =>
                    setFilters((prev) => ({
                      ...prev,
                      offset: (prev.offset ?? 0) + (prev.limit ?? 20),
                    }))
                  }
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary detail dialog - wider and resizable */}
      <Dialog
        open={!!selectedSummaryId}
        onOpenChange={(open) => !open && setSelectedSummaryId(null)}
      >
        <DialogContent className="w-full md:w-[50vw] md:min-w-[600px] max-w-[95vw] h-[70vh] min-h-[400px] max-h-[95vh] resize flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>Summary Details</DialogTitle>
            <DialogDescription>
              AI-generated summary with key insights and themes
            </DialogDescription>
          </DialogHeader>
          {isLoadingSummary ? (
            <div className="space-y-4 py-4 flex-1">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : selectedSummary ? (
            <ScrollArea className="flex-1 min-h-0 pr-4">
              <div className="space-y-6 py-4">
                {/* Executive Summary */}
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">
                    Executive Summary
                  </h4>
                  <p className="text-sm">{selectedSummary.executive_summary}</p>
                </div>

                {/* Key Themes */}
                {(selectedSummary.key_themes?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">
                      Key Themes
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {(selectedSummary.key_themes ?? []).map((theme, i) => (
                        <Badge key={i} variant="secondary">
                          {theme}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Strategic Insights */}
                {(selectedSummary.strategic_insights?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">
                      Strategic Insights
                    </h4>
                    <ul className="list-disc list-inside space-y-1">
                      {(selectedSummary.strategic_insights ?? []).map((insight, i) => (
                        <li key={i} className="text-sm">
                          {insight}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Technical Details */}
                {(selectedSummary.technical_details?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">
                      Technical Details
                    </h4>
                    <ul className="list-disc list-inside space-y-1">
                      {(selectedSummary.technical_details ?? []).map((detail, i) => (
                        <li key={i} className="text-sm">
                          {detail}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Actionable Items */}
                {(selectedSummary.actionable_items?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">
                      Actionable Items
                    </h4>
                    <ul className="list-disc list-inside space-y-1">
                      {(selectedSummary.actionable_items ?? []).map((item, i) => (
                        <li key={i} className="text-sm">
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Metadata */}
                <div className="pt-4 border-t">
                  <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
                    <div>
                      <span className="text-muted-foreground">Model:</span>{" "}
                      <span className="font-medium">{selectedSummary.model_used}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Processing:</span>{" "}
                      <span className="font-medium">
                        {selectedSummary.processing_time_seconds?.toFixed(1)}s
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Tokens:</span>{" "}
                      <span className="font-medium">
                        {selectedSummary.token_usage?.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          ) : null}
          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={() => setSelectedSummaryId(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Generate summaries dialog */}
      <GenerateSummaryDialog
        open={showGenerateDialog}
        onOpenChange={setShowGenerateDialog}
        onGenerate={handleGenerateSummaries}
        isGenerating={summarizeMutation.isPending || summarizeMutation.isProcessing}
        pendingCount={pendingCount}
        failedCount={failedCount}
      />
    </PageContainer>
  )
}

/**
 * Summary row component
 */
function SummaryRow({
  summary,
  onView,
}: {
  summary: SummaryListItem
  onView: () => void
}) {
  return (
    <TableRow className="hover:bg-muted/50">
      <TableCell>
        <div className="flex items-start gap-2">
          {/* Action buttons on the left */}
          <div className="flex items-center gap-1 shrink-0 pt-0.5">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={onView}
              title="View summary details"
              aria-label="View summary details"
            >
              <Eye className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              asChild
            >
              <Link
                to="/review/summary/$id"
                params={{ id: String(summary.content_id) }}
                search={{ source: "content" }}
                title="Review summary side-by-side"
                aria-label="Review summary side-by-side"
              >
                <FileSearch className="h-4 w-4" />
              </Link>
            </Button>
          </div>
          {/* Title and description - clickable to view content */}
          <div
            className="flex-1 cursor-pointer"
            onClick={onView}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && onView()}
          >
            <div className="font-medium line-clamp-1">
              <span className="text-muted-foreground font-normal">[{summary.content_id}]</span>{" "}
              {summary.title}
            </div>
            <div className="text-sm text-muted-foreground line-clamp-1">
              {summary.publication ?? "Unknown"} • {summary.executive_summary_preview}
            </div>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {(summary.key_themes ?? []).slice(0, 3).map((theme, i) => (
            <Badge key={i} variant="outline" className="text-xs">
              {theme}
            </Badge>
          ))}
          {(summary.key_themes?.length ?? 0) > 3 && (
            <Badge variant="outline" className="text-xs">
              +{(summary.key_themes?.length ?? 0) - 3}
            </Badge>
          )}
        </div>
      </TableCell>
      <TableCell>
        <Badge variant="secondary" className="gap-1">
          <Zap className="h-3 w-3" />
          {summary.model_used?.split("-").slice(-2).join("-") ?? "Unknown"}
        </Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {summary.processing_time_seconds?.toFixed(1) ?? "?"}s
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {summary.created_at
            ? formatDistanceToNow(new Date(summary.created_at), { addSuffix: true })
            : "Unknown"}
        </span>
      </TableCell>
    </TableRow>
  )
}
