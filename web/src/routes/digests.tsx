/**
 * Digests Page
 *
 * Displays daily and weekly digest documents.
 * Supports review workflow and revision.
 *
 * Route: /digests
 */

import * as React from "react"
import { useState } from "react"
import { createRoute, Link } from "@tanstack/react-router"
import {
  FileText,
  Plus,
  RefreshCw,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  Eye,
  ThumbsUp,
  ThumbsDown,
  Newspaper,
  Lightbulb,
  TrendingUp,
  Cpu,
  FileSearch,
  MessageSquare,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
} from "lucide-react"
import { formatDistanceToNow, format } from "date-fns"
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
import { SearchInput } from "@/components/ui/search-input"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  useDigests,
  useDigestStats,
  useDigest,
  useGenerateDigest,
  useApproveDigest,
  useRejectDigest,
} from "@/hooks"
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext"
import {
  GenerateDigestDialog,
  type DigestGenerationParams,
} from "@/components/generation"
import type { DigestListItem, DigestStatus, DigestSection, DigestFilters } from "@/types"

export const DigestsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "digests",
  component: DigestsPage,
})

/**
 * Status badge configuration
 */
const statusConfig: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  PENDING: {
    label: "Pending",
    variant: "secondary",
    icon: <Clock className="h-3 w-3" />,
  },
  GENERATING: {
    label: "Generating",
    variant: "outline",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  COMPLETED: {
    label: "Completed",
    variant: "default",
    icon: <CheckCircle className="h-3 w-3" />,
  },
  FAILED: {
    label: "Failed",
    variant: "destructive",
    icon: <AlertCircle className="h-3 w-3" />,
  },
  PENDING_REVIEW: {
    label: "Pending Review",
    variant: "secondary",
    icon: <Eye className="h-3 w-3" />,
  },
  APPROVED: {
    label: "Approved",
    variant: "default",
    icon: <CheckCircle className="h-3 w-3" />,
  },
  REJECTED: {
    label: "Rejected",
    variant: "destructive",
    icon: <AlertCircle className="h-3 w-3" />,
  },
  DELIVERED: {
    label: "Delivered",
    variant: "default",
    icon: <CheckCircle className="h-3 w-3" />,
  },
}

function DigestsPage() {
  const [filters, setFilters] = useState<DigestFilters>({})
  const [searchValue, setSearchValue] = useState("")
  const [selectedDigestId, setSelectedDigestId] = useState<number | null>(null)
  const [showGenerateDialog, setShowGenerateDialog] = useState(false)

  const handleSort = (column: string, order: "asc" | "desc" | undefined) => {
    setFilters((prev) => ({
      ...prev,
      sort_by: order ? column : undefined,
      sort_order: order,
    }))
  }

  const { data: digests, isLoading, isError, error, refetch } = useDigests(filters)
  const { data: stats } = useDigestStats()
  const { data: selectedDigest, isLoading: isLoadingDigest } = useDigest(
    selectedDigestId ?? 0,
    { enabled: !!selectedDigestId }
  )
  const generateMutation = useGenerateDigest()
  const approveMutation = useApproveDigest()
  const rejectMutation = useRejectDigest()
  const { addTask, updateTask, completeTask, failTask } = useBackgroundTasks()

  const handleGenerateDigest = (params: DigestGenerationParams) => {
    // Close dialog immediately - task runs in background
    setShowGenerateDialog(false)

    // Add background task
    const taskId = addTask({
      type: "digest",
      title: `${params.digest_type === "daily" ? "Daily" : "Weekly"} Digest`,
      message: "Starting generation...",
    })

    generateMutation.mutate(
      {
        digest_type: params.digest_type,
        period_start: params.period_start,
        period_end: params.period_end,
        max_strategic_insights: params.max_strategic_insights,
        max_technical_developments: params.max_technical_developments,
        max_emerging_trends: params.max_emerging_trends,
      },
      {
        onSuccess: () => {
          // API returns "queued" - actual work happens in background
          // Poll for completion by checking digest list
          updateTask(taskId, { progress: 20, message: "Generating digest content..." })

          let pollCount = 0
          const maxPolls = 60 // 5 minutes max (5s intervals)

          const pollInterval = setInterval(async () => {
            pollCount++
            const progressPercent = Math.min(20 + pollCount * 1.3, 95)
            updateTask(taskId, {
              progress: Math.round(progressPercent),
              message: pollCount < 10 ? "Analyzing summaries..." :
                       pollCount < 20 ? "Building strategic insights..." :
                       pollCount < 30 ? "Identifying trends..." : "Finalizing digest..."
            })

            // Refetch to check status
            const result = await refetch()
            const newDigest = result.data?.find(
              (d) => d.status === "PENDING_REVIEW" || d.status === "COMPLETED"
            )

            if (newDigest || pollCount >= maxPolls) {
              clearInterval(pollInterval)
              if (newDigest) {
                completeTask(taskId, "Digest generated successfully")
                toast.success(`${params.digest_type === "daily" ? "Daily" : "Weekly"} digest generated`)
              } else {
                updateTask(taskId, { progress: 95, message: "Generation in progress..." })
              }
            }
          }, 5000)
        },
        onError: (err) => {
          const errorMsg = err instanceof Error ? err.message : "Unknown error"
          failTask(taskId, errorMsg)
          toast.error(`Failed to generate digest: ${errorMsg}`)
        },
      }
    )

    // Update progress indicator
    updateTask(taskId, { progress: 10, message: "Queuing generation..." })
  }

  const handleApprove = (digestId: number) => {
    approveMutation.mutate(
      { digestId, reviewer: "user" },
      {
        onSuccess: () => {
          setSelectedDigestId(null)
          refetch()
        },
      }
    )
  }

  const handleReject = (digestId: number) => {
    rejectMutation.mutate(
      { digestId, reviewer: "user", reason: "Rejected via UI" },
      {
        onSuccess: () => {
          setSelectedDigestId(null)
          refetch()
        },
      }
    )
  }

  // Filter digests by search
  const filteredDigests = digests?.filter((digest) => {
    if (!searchValue) return true
    return digest.title?.toLowerCase().includes(searchValue.toLowerCase())
  })

  return (
    <PageContainer
      title="Digests"
      description="Daily and weekly aggregated reports for your audience"
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button onClick={() => setShowGenerateDialog(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Generate Digest
          </Button>
        </div>
      }
    >
      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total</CardDescription>
              <CardTitle className="text-2xl">{stats.total}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Pending Review</CardDescription>
              <CardTitle className="text-2xl">{stats.pending_review}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Approved</CardDescription>
              <CardTitle className="text-2xl">{stats.approved}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Delivered</CardDescription>
              <CardTitle className="text-2xl">{stats.delivered}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Digest list */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Digest List</CardTitle>
          </div>
          <CardDescription>
            {digests?.length ?? 0} digests
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filter row */}
          <div className="mb-4 flex flex-col gap-4 md:flex-row">
            <div className="relative flex-1">
              <SearchInput
                placeholder="Search digests..."
                aria-label="Search digests"
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                onClear={() => setSearchValue("")}
              />
            </div>
            <Select
              value={filters.digest_type ?? "all"}
              onValueChange={(value) =>
                setFilters((prev) => ({
                  ...prev,
                  digest_type: value === "all" ? undefined : (value as "daily" | "weekly"),
                }))
              }
            >
              <SelectTrigger className="w-[140px]" aria-label="Filter by type">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={filters.status ?? "all"}
              onValueChange={(value) =>
                setFilters((prev) => ({
                  ...prev,
                  status: value === "all" ? undefined : (value as DigestStatus),
                }))
              }
            >
              <SelectTrigger className="w-[180px]" aria-label="Filter by status">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="PENDING_REVIEW">Pending Review</SelectItem>
                <SelectItem value="APPROVED">Approved</SelectItem>
                <SelectItem value="GENERATING">Generating</SelectItem>
                <SelectItem value="FAILED">Failed</SelectItem>
                <SelectItem value="DELIVERED">Delivered</SelectItem>
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
                  Error loading digests: {error?.message}
                </p>
                <Button className="mt-4" size="sm" onClick={() => refetch()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Retry
                </Button>
              </div>
            </div>
          ) : !filteredDigests?.length ? (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
              <div className="text-center">
                <FileText className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  No digests found
                </p>
                <p className="text-xs text-muted-foreground">
                  Generate a daily or weekly digest to get started
                </p>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <SortableTableHead
                    column="digest_type"
                    label="Type"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[100px]"
                  />
                  <SortableTableHead
                    column="period_start"
                    label="Period"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[200px]"
                  />
                  <TableHead className="w-[80px]">Sources</TableHead>
                  <SortableTableHead
                    column="status"
                    label="Status"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[150px]"
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
                {filteredDigests.map((digest) => (
                  <DigestRow
                    key={digest.id}
                    digest={digest}
                    onView={() => setSelectedDigestId(digest.id)}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Digest detail dialog */}
      <Dialog
        open={!!selectedDigestId}
        onOpenChange={(open) => !open && setSelectedDigestId(null)}
      >
        <DialogContent className="w-full md:w-[50vw] md:min-w-[600px] max-w-[95vw] h-[70vh] min-h-[400px] max-h-[95vh] resize flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>{selectedDigest?.title ?? "Digest Details"}</DialogTitle>
            <DialogDescription>
              {selectedDigest?.digest_type === "daily" ? "Daily" : "Weekly"} digest
              {selectedDigest?.period_start && selectedDigest?.period_end && (
                <> covering {format(new Date(selectedDigest.period_start), "MMM d")} - {format(new Date(selectedDigest.period_end), "MMM d, yyyy")}</>
              )}
            </DialogDescription>
          </DialogHeader>
          {isLoadingDigest ? (
            <div className="space-y-4 py-4 flex-1">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : selectedDigest ? (
            <ScrollArea className="flex-1 min-h-0 pr-4">
              <div className="space-y-6 py-4">
                {/* Metadata row */}
                <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
                  <div>
                    <span className="text-muted-foreground">Content Items:</span>{" "}
                    <span className="font-medium">{selectedDigest.content_count}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Model:</span>{" "}
                    <span className="font-medium">{selectedDigest.model_used}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Revisions:</span>{" "}
                    <span className="font-medium">{selectedDigest.revision_count}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Status:</span>{" "}
                    <Badge variant="secondary">{selectedDigest.status}</Badge>
                  </div>
                </div>

                {/* Executive Overview */}
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Executive Overview
                  </h4>
                  <p className="text-sm whitespace-pre-wrap">
                    {selectedDigest.executive_overview}
                  </p>
                </div>

                {/* Tabbed sections */}
                <Tabs defaultValue="strategic" className="w-full">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="strategic" className="flex items-center gap-1">
                      <Lightbulb className="h-3 w-3" />
                      Strategic ({selectedDigest.strategic_insights?.length ?? 0})
                    </TabsTrigger>
                    <TabsTrigger value="technical" className="flex items-center gap-1">
                      <Cpu className="h-3 w-3" />
                      Technical ({selectedDigest.technical_developments?.length ?? 0})
                    </TabsTrigger>
                    <TabsTrigger value="trends" className="flex items-center gap-1">
                      <TrendingUp className="h-3 w-3" />
                      Trends ({selectedDigest.emerging_trends?.length ?? 0})
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value="strategic" className="mt-4">
                    <SectionList sections={selectedDigest.strategic_insights} />
                  </TabsContent>
                  <TabsContent value="technical" className="mt-4">
                    <SectionList sections={selectedDigest.technical_developments} />
                  </TabsContent>
                  <TabsContent value="trends" className="mt-4">
                    <SectionList sections={selectedDigest.emerging_trends} />
                  </TabsContent>
                </Tabs>

                {/* Recommendations */}
                {selectedDigest.actionable_recommendations && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">
                      Actionable Recommendations
                    </h4>
                    <div className="grid gap-4 md:grid-cols-3">
                      {Object.entries(selectedDigest.actionable_recommendations).map(
                        ([role, items]) => (
                          <div key={role} className="p-3 rounded-lg border">
                            <h5 className="text-xs font-medium mb-2 capitalize">
                              {role.replace(/_/g, " ")}
                            </h5>
                            <ul className="text-xs space-y-1">
                              {(items as string[])?.map((item, i) => (
                                <li key={i} className="flex gap-2">
                                  <span className="text-muted-foreground">•</span>
                                  {item}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                )}

                {/* Sources */}
                {selectedDigest.sources && selectedDigest.sources.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                      <Newspaper className="h-4 w-4" />
                      Sources ({selectedDigest.sources.length})
                    </h4>
                    <div className="grid gap-2">
                      {selectedDigest.sources.slice(0, 10).map((source, i) => (
                        <div key={i} className="text-xs p-2 rounded border">
                          <span className="font-medium">{source.title}</span>
                          {source.publication && (
                            <span className="text-muted-foreground"> - {source.publication}</span>
                          )}
                          {source.date && (
                            <span className="text-muted-foreground"> ({source.date})</span>
                          )}
                        </div>
                      ))}
                      {selectedDigest.sources.length > 10 && (
                        <p className="text-xs text-muted-foreground">
                          ... and {selectedDigest.sources.length - 10} more sources
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>
          ) : null}
          <DialogFooter className="shrink-0 flex gap-2">
            <Button variant="outline" onClick={() => setSelectedDigestId(null)}>
              Close
            </Button>
            {selectedDigestId && selectedDigest?.status === "PENDING_REVIEW" && (
              <>
                <Button
                  variant="destructive"
                  onClick={() => handleReject(selectedDigestId)}
                  disabled={rejectMutation.isPending}
                >
                  <ThumbsDown className="mr-2 h-4 w-4" />
                  Reject
                </Button>
                <Button
                  onClick={() => handleApprove(selectedDigestId)}
                  disabled={approveMutation.isPending}
                >
                  <ThumbsUp className="mr-2 h-4 w-4" />
                  Approve
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Generate digest dialog */}
      <GenerateDigestDialog
        open={showGenerateDialog}
        onOpenChange={setShowGenerateDialog}
        onGenerate={handleGenerateDigest}
        isGenerating={generateMutation.isPending}
      />
    </PageContainer>
  )
}

/**
 * Section list component
 */
function SectionList({ sections }: { sections?: DigestSection[] }) {
  if (!sections || sections.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-4">
        No items in this section
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {sections.map((section, i) => (
        <div key={i} className="p-3 rounded-lg border">
          <h5 className="font-medium text-sm mb-1">{section.title}</h5>
          <p className="text-xs text-muted-foreground mb-2">{section.summary}</p>
          {section.details && section.details.length > 0 && (
            <ul className="text-xs space-y-1">
              {section.details.map((detail, j) => (
                <li key={j} className="flex gap-2">
                  <span className="text-muted-foreground">•</span>
                  {detail}
                </li>
              ))}
            </ul>
          )}
          {section.themes && section.themes.length > 0 && (
            <div className="flex gap-1 mt-2 flex-wrap">
              {section.themes.map((theme, j) => (
                <Badge key={j} variant="outline" className="text-xs">
                  {theme}
                </Badge>
              ))}
            </div>
          )}
          {section.followup_prompts && section.followup_prompts.length > 0 && (
            <FollowUpPromptsSection prompts={section.followup_prompts} />
          )}
        </div>
      ))}
    </div>
  )
}

/**
 * Collapsible follow-up prompts with copy-to-clipboard
 */
function FollowUpPromptsSection({ prompts }: { prompts: string[] }) {
  const [isOpen, setIsOpen] = React.useState(false)

  return (
    <div className="mt-2">
      <Button
        variant="ghost"
        size="sm"
        className="h-auto gap-1.5 px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <MessageSquare className="h-3 w-3" />
        Follow-up prompts ({prompts.length})
        {isOpen ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
      </Button>
      {isOpen && (
        <div className="mt-2 space-y-2">
          {prompts.map((prompt, idx) => (
            <CopyablePromptItem key={idx} prompt={prompt} />
          ))}
        </div>
      )}
    </div>
  )
}

function CopyablePromptItem({ prompt }: { prompt: string }) {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(prompt)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="group relative rounded-md border bg-muted/30 p-2.5 pr-9 text-xs leading-relaxed">
      {prompt}
      <Button
        variant="ghost"
        size="sm"
        className="absolute right-1 top-1 h-6 w-6 p-0 opacity-0 transition-opacity group-hover:opacity-100"
        onClick={handleCopy}
        title="Copy prompt"
      >
        {copied ? (
          <Check className="h-3 w-3 text-green-500" />
        ) : (
          <Copy className="h-3 w-3" />
        )}
      </Button>
    </div>
  )
}

/**
 * Digest row component
 */
function DigestRow({
  digest,
  onView,
}: {
  digest: DigestListItem
  onView: () => void
}) {
  const status = statusConfig[digest.status] ?? {
    label: digest.status,
    variant: "outline" as const,
    icon: null,
  }

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
              title="View digest"
              aria-label="View digest"
            >
              <Eye className="h-4 w-4" />
            </Button>
            {(digest.status === "PENDING_REVIEW" || digest.status === "COMPLETED" || digest.status === "APPROVED") && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                asChild
              >
                <Link
                  to="/review/digest/$id"
                  params={{ id: String(digest.id) }}
                  title="Review digest"
                  aria-label="Review digest"
                >
                  <FileSearch className="h-4 w-4" />
                </Link>
              </Button>
            )}
          </div>
          {/* Title - clickable to view */}
          <div
            className="flex-1 cursor-pointer"
            onClick={onView}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && onView()}
          >
            <div className="font-medium line-clamp-1">
              {digest.title ?? `Digest #${digest.id}`}
            </div>
            <div className="text-sm text-muted-foreground">
              {digest.model_used}
            </div>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="capitalize">
          {digest.digest_type}
        </Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {digest.period_start && digest.period_end
            ? `${format(new Date(digest.period_start), "MMM d")} - ${format(new Date(digest.period_end), "MMM d")}`
            : "Unknown"}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {digest.content_count}
        </span>
      </TableCell>
      <TableCell>
        <Badge variant={status.variant} className="gap-1">
          {status.icon}
          {status.label}
        </Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {digest.created_at
            ? formatDistanceToNow(new Date(digest.created_at), { addSuffix: true })
            : "Unknown"}
        </span>
      </TableCell>
    </TableRow>
  )
}
