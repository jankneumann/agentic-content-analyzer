/**
 * Summaries Page
 *
 * Displays AI-generated summaries of newsletters.
 * Allows viewing summary details and triggering summarization.
 *
 * Route: /summaries
 */

import { useState } from "react"
import { createRoute } from "@tanstack/react-router"
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
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"

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
  useTriggerSummarization,
} from "@/hooks"
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

  const { data, isLoading, isError, error, refetch } = useSummaries(filters)
  const { data: stats } = useSummaryStats()
  const summarizeMutation = useTriggerSummarization()

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
      modelUsed: value === "all" ? undefined : value,
      offset: 0,
    }))
  }

  const handleSummarizeAll = () => {
    summarizeMutation.mutate(
      { newsletterIds: [] }, // Empty = all pending
      {
        onSuccess: () => {
          refetch()
        },
      }
    )
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
          <Button
            onClick={handleSummarizeAll}
            disabled={summarizeMutation.isPending || summarizeMutation.isProcessing}
          >
            {summarizeMutation.isPending || summarizeMutation.isProcessing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Summarizing...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Summarize Pending
              </>
            )}
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
                  Summarizing newsletters... ({summarizeMutation.progress.progress}%)
                </p>
                <p className="text-xs text-muted-foreground">
                  {summarizeMutation.progress.step}
                </p>
              </div>
              <Badge variant="outline">
                {summarizeMutation.progress.completedCount} / {summarizeMutation.progress.totalCount}
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
                {stats.avgProcessingTime?.toFixed(1) ?? "0"}s
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Avg Tokens</CardDescription>
              <CardTitle className="text-2xl">
                {Math.round(stats.avgTokenUsage ?? 0).toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Models Used</CardDescription>
              <CardTitle className="text-2xl">
                {Object.keys(stats.byModel ?? {}).length}
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
              value={filters.modelUsed ?? "all"}
              onValueChange={handleModelFilter}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Model" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Models</SelectItem>
                {stats?.byModel &&
                  Object.keys(stats.byModel).map((model) => (
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
                  Ingest newsletters first, then generate summaries
                </p>
                <Button
                  className="mt-4"
                  size="sm"
                  onClick={handleSummarizeAll}
                  disabled={summarizeMutation.isPending}
                >
                  <Play className="mr-2 h-4 w-4" />
                  Summarize Pending
                </Button>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Newsletter</TableHead>
                  <TableHead className="w-[200px]">Key Themes</TableHead>
                  <TableHead className="w-[120px]">Model</TableHead>
                  <TableHead className="w-[100px]">Time</TableHead>
                  <TableHead className="w-[130px]">Created</TableHead>
                  <TableHead className="w-[60px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((summary) => (
                  <SummaryRow
                    key={summary.id}
                    summary={summary}
                    onView={() => setSelectedSummaryId(summary.id)}
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
                  disabled={!data.hasMore}
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

      {/* Summary detail dialog */}
      <Dialog
        open={!!selectedSummaryId}
        onOpenChange={(open) => !open && setSelectedSummaryId(null)}
      >
        <DialogContent className="max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Summary Details</DialogTitle>
            <DialogDescription>
              AI-generated summary with key insights and themes
            </DialogDescription>
          </DialogHeader>
          {isLoadingSummary ? (
            <div className="space-y-4 py-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : selectedSummary ? (
            <ScrollArea className="max-h-[60vh] pr-4">
              <div className="space-y-6 py-4">
                {/* Executive Summary */}
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">
                    Executive Summary
                  </h4>
                  <p className="text-sm">{selectedSummary.executiveSummary}</p>
                </div>

                {/* Key Themes */}
                {(selectedSummary.keyThemes?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">
                      Key Themes
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {(selectedSummary.keyThemes ?? []).map((theme, i) => (
                        <Badge key={i} variant="secondary">
                          {theme}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Strategic Insights */}
                {(selectedSummary.strategicInsights?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">
                      Strategic Insights
                    </h4>
                    <ul className="list-disc list-inside space-y-1">
                      {(selectedSummary.strategicInsights ?? []).map((insight, i) => (
                        <li key={i} className="text-sm">
                          {insight}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Technical Details */}
                {(selectedSummary.technicalDetails?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">
                      Technical Details
                    </h4>
                    <ul className="list-disc list-inside space-y-1">
                      {(selectedSummary.technicalDetails ?? []).map((detail, i) => (
                        <li key={i} className="text-sm">
                          {detail}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Actionable Items */}
                {(selectedSummary.actionableItems?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">
                      Actionable Items
                    </h4>
                    <ul className="list-disc list-inside space-y-1">
                      {(selectedSummary.actionableItems ?? []).map((item, i) => (
                        <li key={i} className="text-sm">
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Metadata */}
                <div className="pt-4 border-t">
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Model:</span>{" "}
                      <span className="font-medium">{selectedSummary.modelUsed}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Processing:</span>{" "}
                      <span className="font-medium">
                        {selectedSummary.processingTimeSeconds?.toFixed(1)}s
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Tokens:</span>{" "}
                      <span className="font-medium">
                        {selectedSummary.tokenUsage?.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedSummaryId(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
    <TableRow className="cursor-pointer hover:bg-muted/50" onClick={onView}>
      <TableCell>
        <div>
          <div className="font-medium line-clamp-1">
            {summary.newsletterTitle ?? `Newsletter #${summary.newsletterId ?? "?"}`}
          </div>
          <div className="text-sm text-muted-foreground line-clamp-1">
            {summary.executiveSummaryPreview}
          </div>
        </div>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {(summary.keyThemes ?? []).slice(0, 3).map((theme, i) => (
            <Badge key={i} variant="outline" className="text-xs">
              {theme}
            </Badge>
          ))}
          {(summary.keyThemes?.length ?? 0) > 3 && (
            <Badge variant="outline" className="text-xs">
              +{(summary.keyThemes?.length ?? 0) - 3}
            </Badge>
          )}
        </div>
      </TableCell>
      <TableCell>
        <Badge variant="secondary" className="gap-1">
          <Zap className="h-3 w-3" />
          {summary.modelUsed?.split("-").slice(-2).join("-") ?? "Unknown"}
        </Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {summary.processingTimeSeconds?.toFixed(1) ?? "?"}s
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {summary.createdAt
            ? formatDistanceToNow(new Date(summary.createdAt), { addSuffix: true })
            : "Unknown"}
        </span>
      </TableCell>
      <TableCell>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Eye className="h-4 w-4" />
        </Button>
      </TableCell>
    </TableRow>
  )
}
