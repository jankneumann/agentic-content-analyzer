/**
 * Contents Page
 *
 * Displays a list of unified content with filtering and search.
 * The Content model unifies newsletters, documents, and other sources.
 * Allows triggering new ingestion from Gmail, RSS feeds, or YouTube.
 *
 * Route: /contents
 */

import { useState } from "react"
import { createRoute, Link } from "@tanstack/react-router"
import {
  FileText,
  RefreshCw,
  Search,
  Mail,
  Rss,
  Youtube,
  Upload,
  Globe,
  CheckCircle,
  Clock,
  AlertCircle,
  Loader2,
  FileSearch,
  Eye,
  ExternalLink,
  Plus,
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import ReactMarkdown from "react-markdown"
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
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useContents, useContent, useContentStats, useIngestContents } from "@/hooks/use-contents"
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext"
import {
  IngestContentsDialog,
  type IngestContentParams,
} from "@/components/generation"
import type { ContentStatus, ContentSource, ContentFilters } from "@/types"

/**
 * Route definition
 */
export const ContentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "contents",
  component: ContentsPage,
})

/**
 * Status badge configuration
 */
const statusConfig: Record<
  ContentStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  pending: {
    label: "Pending",
    variant: "secondary",
    icon: <Clock className="h-3 w-3" />,
  },
  parsing: {
    label: "Parsing",
    variant: "outline",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  parsed: {
    label: "Parsed",
    variant: "outline",
    icon: <CheckCircle className="h-3 w-3" />,
  },
  processing: {
    label: "Processing",
    variant: "outline",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  completed: {
    label: "Completed",
    variant: "default",
    icon: <CheckCircle className="h-3 w-3" />,
  },
  failed: {
    label: "Failed",
    variant: "destructive",
    icon: <AlertCircle className="h-3 w-3" />,
  },
}

/**
 * Source badge configuration
 */
const sourceConfig: Record<
  ContentSource,
  { label: string; icon: React.ReactNode }
> = {
  gmail: {
    label: "Gmail",
    icon: <Mail className="h-3 w-3" />,
  },
  rss: {
    label: "RSS",
    icon: <Rss className="h-3 w-3" />,
  },
  youtube: {
    label: "YouTube",
    icon: <Youtube className="h-3 w-3" />,
  },
  file_upload: {
    label: "Upload",
    icon: <Upload className="h-3 w-3" />,
  },
  manual: {
    label: "Manual",
    icon: <FileText className="h-3 w-3" />,
  },
  webpage: {
    label: "Webpage",
    icon: <Globe className="h-3 w-3" />,
  },
  other: {
    label: "Other",
    icon: <FileText className="h-3 w-3" />,
  },
}

/**
 * Contents page component
 */
function ContentsPage() {
  const [filters, setFilters] = useState<ContentFilters>({
    page: 1,
    page_size: 20,
  })
  const [searchValue, setSearchValue] = useState("")
  const [selectedContentId, setSelectedContentId] = useState<number | null>(null)
  const [ingestDialogOpen, setIngestDialogOpen] = useState(false)

  const { data, isLoading, isError, error, refetch } = useContents(filters)
  const { data: stats } = useContentStats()
  const ingestMutation = useIngestContents()
  const { addTask, updateTask, completeTask, failTask } = useBackgroundTasks()

  // Fetch selected content details
  const { data: selectedContent, isLoading: isLoadingContent } = useContent(
    selectedContentId ?? 0,
    { enabled: !!selectedContentId }
  )

  const handleSearch = (value: string) => {
    setSearchValue(value)
    setFilters((prev) => ({ ...prev, search: value || undefined, page: 1 }))
  }

  const handleStatusFilter = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      status: value === "all" ? undefined : (value as ContentStatus),
      page: 1,
    }))
  }

  const handleSourceFilter = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      source_type: value === "all" ? undefined : (value as ContentSource),
      page: 1,
    }))
  }

  const getSourceName = (source: ContentSource) => {
    switch (source) {
      case "gmail":
        return "Gmail"
      case "rss":
        return "RSS"
      case "youtube":
        return "YouTube"
      default:
        return source
    }
  }

  const handleIngest = (params: IngestContentParams) => {
    // Close dialog immediately - task runs in background
    setIngestDialogOpen(false)

    const sourceName = getSourceName(params.source)

    // Add background task
    const taskId = addTask({
      type: "ingest",
      title: `Ingest from ${sourceName}`,
      message: "Starting ingestion...",
    })

    // Track initial count for comparison
    const initialCount = data?.total ?? 0

    ingestMutation.mutate(
      {
        source: params.source,
        max_results: params.max_results,
        days_back: params.days_back,
        force_reprocess: params.force_reprocess,
      },
      {
        onSuccess: () => {
          // API returns "queued" - actual work happens in background
          // Poll for completion by checking for new content
          updateTask(taskId, { progress: 20, message: `Fetching from ${sourceName}...` })

          let pollCount = 0
          const maxPolls = 60 // 5 minutes max (5s intervals)

          const pollInterval = setInterval(async () => {
            pollCount++
            const progressPercent = Math.min(20 + pollCount * 1.3, 95)
            updateTask(taskId, {
              progress: Math.round(progressPercent),
              message:
                pollCount < 10
                  ? `Connecting to ${sourceName}...`
                  : pollCount < 20
                    ? "Fetching content..."
                    : pollCount < 30
                      ? "Processing content..."
                      : "Finalizing ingestion...",
            })

            const result = await refetch()
            const newCount = result.data?.total ?? 0

            // Check if we have new content or if we've been polling too long
            if (newCount > initialCount || pollCount >= maxPolls) {
              clearInterval(pollInterval)
              if (newCount > initialCount) {
                const ingestedCount = newCount - initialCount
                completeTask(taskId, `Ingested ${ingestedCount} content item${ingestedCount > 1 ? "s" : ""}`)
                toast.success(`Ingested ${ingestedCount} content item${ingestedCount > 1 ? "s" : ""} from ${sourceName}`)
              } else {
                // No new content found - could be duplicates or empty source
                completeTask(taskId, "No new content found")
                toast.info(`No new content found in ${sourceName}`)
              }
            }
          }, 5000)
        },
        onError: (err) => {
          const errorMsg = err instanceof Error ? err.message : "Unknown error"
          failTask(taskId, errorMsg)
          toast.error(`Failed to ingest: ${errorMsg}`)
        },
      }
    )

    // Update progress indicator
    updateTask(taskId, { progress: 10, message: "Queuing ingestion..." })
  }

  return (
    <PageContainer
      title="Contents"
      description="Unified content from Gmail, RSS feeds, YouTube, and uploads"
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button onClick={() => setIngestDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Ingest New
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
              <CardDescription>Pending</CardDescription>
              <CardTitle className="text-2xl">{stats.pending_count}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Completed</CardDescription>
              <CardTitle className="text-2xl">{stats.completed_count}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Failed</CardDescription>
              <CardTitle className="text-2xl">{stats.failed_count}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Content List</CardTitle>
          </div>
          <CardDescription>
            {data?.total ?? 0} content items found
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filter row */}
          <div className="mb-4 flex flex-col gap-4 md:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search contents..."
                value={searchValue}
                onChange={(e) => handleSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={filters.status ?? "all"}
              onValueChange={handleStatusFilter}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="parsing">Parsing</SelectItem>
                <SelectItem value="parsed">Parsed</SelectItem>
                <SelectItem value="processing">Processing</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={filters.source_type ?? "all"}
              onValueChange={handleSourceFilter}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Source" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sources</SelectItem>
                <SelectItem value="gmail">Gmail</SelectItem>
                <SelectItem value="rss">RSS</SelectItem>
                <SelectItem value="youtube">YouTube</SelectItem>
                <SelectItem value="file_upload">File Upload</SelectItem>
                <SelectItem value="manual">Manual</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
              <div className="text-center">
                <AlertCircle className="mx-auto h-12 w-12 text-destructive/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  Error loading contents: {error?.message}
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
                <FileText className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  No contents found
                </p>
                <Button
                  className="mt-4"
                  size="sm"
                  onClick={() => setIngestDialogOpen(true)}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Ingest Content
                </Button>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[80px]">Actions</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead className="w-[120px]">Source</TableHead>
                  <TableHead className="w-[150px]">Publication</TableHead>
                  <TableHead className="w-[120px]">Status</TableHead>
                  <TableHead className="w-[150px]">Published</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((content) => {
                  const status = statusConfig[content.status]
                  const source = sourceConfig[content.source_type]
                  return (
                    <TableRow key={content.id}>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => setSelectedContentId(content.id)}
                            title="View content"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {content.status === "completed" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              asChild
                            >
                              <Link
                                to="/review/summary/$id"
                                params={{ id: String(content.id) }}
                                search={{ source: "content" }}
                                title="Review summary"
                              >
                                <FileSearch className="h-4 w-4" />
                              </Link>
                            </Button>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium line-clamp-1">
                            <span className="text-muted-foreground font-normal">[{content.id}]</span>{" "}
                            {content.title}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="gap-1">
                          {source.icon}
                          {source.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground">
                          {content.publication ?? "-"}
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
                          {content.published_date
                            ? formatDistanceToNow(new Date(content.published_date), {
                                addSuffix: true,
                              })
                            : "Unknown"}
                        </span>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {data && data.total > (data.page_size ?? 20) && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Page {data.page} of {Math.ceil(data.total / (data.page_size ?? 20))}
                {" "}({data.total} items)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!data.has_prev}
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
                  disabled={!data.has_next}
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
        </CardContent>
      </Card>

      {/* Content detail dialog */}
      <Dialog
        open={!!selectedContentId}
        onOpenChange={(open) => !open && setSelectedContentId(null)}
      >
        <DialogContent className="w-[50vw] min-w-[600px] max-w-[95vw] max-h-[85vh] resize overflow-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Content Details
            </DialogTitle>
            <DialogDescription>
              {selectedContent?.title ?? "Loading..."}
            </DialogDescription>
          </DialogHeader>

          {isLoadingContent ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : selectedContent ? (
            <div className="space-y-4">
              {/* Metadata */}
              <div className="flex flex-wrap gap-4 text-sm">
                {selectedContent.author && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground">Author:</span>
                    <span className="font-medium">{selectedContent.author}</span>
                  </div>
                )}
                {selectedContent.publication && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground">Publication:</span>
                    <span className="font-medium">{selectedContent.publication}</span>
                  </div>
                )}
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">Source:</span>
                  <Badge variant="outline" className="gap-1">
                    {sourceConfig[selectedContent.source_type].icon}
                    {sourceConfig[selectedContent.source_type].label}
                  </Badge>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">Status:</span>
                  <Badge variant={statusConfig[selectedContent.status].variant} className="gap-1">
                    {statusConfig[selectedContent.status].icon}
                    {statusConfig[selectedContent.status].label}
                  </Badge>
                </div>
                {selectedContent.published_date && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground">Published:</span>
                    <span>{formatDistanceToNow(new Date(selectedContent.published_date), { addSuffix: true })}</span>
                  </div>
                )}
                {selectedContent.parser_used && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground">Parser:</span>
                    <span className="font-mono text-xs">{selectedContent.parser_used}</span>
                  </div>
                )}
              </div>

              {/* Content - Markdown rendering */}
              <div className="border rounded-lg">
                <ScrollArea className="h-[400px]">
                  <div className="p-4">
                    {selectedContent.markdown_content ? (
                      <div className="prose prose-sm max-w-none dark:prose-invert">
                        <ReactMarkdown>
                          {selectedContent.markdown_content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <p className="text-muted-foreground italic">No content available</p>
                    )}
                  </div>
                </ScrollArea>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2">
                {selectedContent.source_url && (
                  <Button variant="outline" asChild>
                    <a
                      href={selectedContent.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink className="mr-2 h-4 w-4" />
                      View Original
                    </a>
                  </Button>
                )}
                {selectedContent.status === "completed" && (
                  <Button asChild>
                    <Link
                      to="/review/summary/$id"
                      params={{ id: String(selectedContent.id) }}
                      search={{ source: "content" }}
                    >
                      <FileSearch className="mr-2 h-4 w-4" />
                      Review Summary
                    </Link>
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center py-8">
              <p className="text-muted-foreground">Content not found</p>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Ingest content dialog */}
      <IngestContentsDialog
        open={ingestDialogOpen}
        onOpenChange={setIngestDialogOpen}
        onIngest={handleIngest}
        isIngesting={ingestMutation.isPending}
      />
    </PageContainer>
  )
}
