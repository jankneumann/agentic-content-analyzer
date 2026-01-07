/**
 * Newsletters Page
 *
 * Displays a list of ingested newsletters with filtering and search.
 * Allows triggering new ingestion from Gmail or RSS feeds.
 *
 * Route: /newsletters
 */

import { useState } from "react"
import { createRoute, Link } from "@tanstack/react-router"
import {
  Newspaper,
  Plus,
  RefreshCw,
  Search,
  Mail,
  Rss,
  CheckCircle,
  Clock,
  AlertCircle,
  Loader2,
  FileSearch,
  Eye,
  ExternalLink,
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
import { useNewsletters, useNewsletter, useIngestNewsletters, useNewsletterStats } from "@/hooks"
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext"
import {
  IngestNewslettersDialog,
  type IngestParams,
} from "@/components/generation"
import type { NewsletterStatus, NewsletterSource, NewsletterFilters } from "@/types"

/**
 * Route definition
 */
export const NewslettersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "newsletters",
  component: NewslettersPage,
})

/**
 * Status badge configuration
 */
const statusConfig: Record<
  NewsletterStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  pending: {
    label: "Pending",
    variant: "secondary",
    icon: <Clock className="h-3 w-3" />,
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
  NewsletterSource,
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
}

/**
 * Newsletters page component
 */
function NewslettersPage() {
  const [filters, setFilters] = useState<NewsletterFilters>({
    limit: 20,
    offset: 0,
  })
  const [searchValue, setSearchValue] = useState("")
  const [ingestDialogOpen, setIngestDialogOpen] = useState(false)
  const [selectedNewsletterId, setSelectedNewsletterId] = useState<string | null>(null)

  const { data, isLoading, isError, error, refetch } = useNewsletters(filters)
  const { data: stats } = useNewsletterStats()
  const ingestMutation = useIngestNewsletters()
  const { addTask, updateTask, completeTask, failTask } = useBackgroundTasks()

  // Fetch selected newsletter details
  const { data: selectedNewsletter, isLoading: isLoadingNewsletter } = useNewsletter(
    selectedNewsletterId ?? "",
    { enabled: !!selectedNewsletterId }
  )

  const handleSearch = (value: string) => {
    setSearchValue(value)
    setFilters((prev) => ({ ...prev, search: value || undefined, offset: 0 }))
  }

  const handleStatusFilter = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      status: value === "all" ? undefined : (value as NewsletterStatus),
      offset: 0,
    }))
  }

  const handleSourceFilter = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      source: value === "all" ? undefined : (value as NewsletterSource),
      offset: 0,
    }))
  }

  const handleIngest = (params: IngestParams) => {
    // Close dialog immediately - task runs in background
    setIngestDialogOpen(false)

    const sourceName = params.source === "gmail" ? "Gmail" : "RSS"

    // Add background task
    const taskId = addTask({
      type: "ingest",
      title: `Ingest from ${sourceName}`,
      message: "Starting ingestion...",
    })

    ingestMutation.mutate(
      {
        source: params.source,
        max_results: params.max_results,
        days_back: params.days_back,
      },
      {
        onSuccess: () => {
          completeTask(taskId, "Ingestion complete")
          toast.success(`Ingested newsletters from ${sourceName}`)
          refetch()
        },
        onError: (err) => {
          const errorMsg = err instanceof Error ? err.message : "Unknown error"
          failTask(taskId, errorMsg)
          toast.error(`Failed to ingest: ${errorMsg}`)
        },
      }
    )

    // Update progress indicator
    updateTask(taskId, { progress: 5, message: `Fetching from ${sourceName}...` })
  }

  return (
    <PageContainer
      title="Newsletters"
      description="Manage ingested newsletters from Gmail and RSS feeds"
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
              <CardTitle className="text-2xl">{stats.by_status?.pending ?? 0}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Summarized</CardDescription>
              <CardTitle className="text-2xl">{stats.by_status?.completed ?? 0}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Failed</CardDescription>
              <CardTitle className="text-2xl">{stats.by_status?.failed ?? 0}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Newspaper className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Newsletter List</CardTitle>
          </div>
          <CardDescription>
            {data?.total ?? 0} newsletters found
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filter row */}
          <div className="mb-4 flex flex-col gap-4 md:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search newsletters..."
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
                <SelectItem value="processing">Processing</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={filters.source ?? "all"}
              onValueChange={handleSourceFilter}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Source" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sources</SelectItem>
                <SelectItem value="gmail">Gmail</SelectItem>
                <SelectItem value="rss">RSS</SelectItem>
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
                  Error loading newsletters: {error?.message}
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
                <Newspaper className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  No newsletters found
                </p>
                <Button
                  className="mt-4"
                  size="sm"
                  onClick={() => setIngestDialogOpen(true)}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Ingest from Gmail
                </Button>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead className="w-[120px]">Source</TableHead>
                  <TableHead className="w-[150px]">Publication</TableHead>
                  <TableHead className="w-[120px]">Status</TableHead>
                  <TableHead className="w-[150px]">Published</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((newsletter) => {
                  const status = statusConfig[newsletter.status]
                  const source = sourceConfig[newsletter.source]
                  return (
                    <TableRow key={newsletter.id}>
                      <TableCell>
                        <div>
                          <div className="font-medium line-clamp-1">
                            <span className="text-muted-foreground font-normal">[{newsletter.id}]</span>{" "}
                            {newsletter.title}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {newsletter.sender}
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
                          {newsletter.publication ?? "-"}
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
                          {newsletter.published_date
                            ? formatDistanceToNow(new Date(newsletter.published_date), {
                                addSuffix: true,
                              })
                            : "Unknown"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => setSelectedNewsletterId(String(newsletter.id))}
                            title="View newsletter"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {newsletter.status === "completed" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              asChild
                            >
                              <Link
                                to="/review/summary/$id"
                                params={{ id: String(newsletter.id) }}
                                title="Review summary"
                              >
                                <FileSearch className="h-4 w-4" />
                              </Link>
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
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
      {/* Newsletter detail dialog */}
      <Dialog
        open={!!selectedNewsletterId}
        onOpenChange={(open) => !open && setSelectedNewsletterId(null)}
      >
        <DialogContent className="max-w-4xl max-h-[85vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Newspaper className="h-5 w-5" />
              Newsletter Details
            </DialogTitle>
            <DialogDescription>
              {selectedNewsletter?.title ?? "Loading..."}
            </DialogDescription>
          </DialogHeader>

          {isLoadingNewsletter ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : selectedNewsletter ? (
            <div className="space-y-4">
              {/* Metadata */}
              <div className="flex flex-wrap gap-4 text-sm">
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">From:</span>
                  <span className="font-medium">{selectedNewsletter.sender}</span>
                </div>
                {selectedNewsletter.publication && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground">Publication:</span>
                    <span className="font-medium">{selectedNewsletter.publication}</span>
                  </div>
                )}
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">Source:</span>
                  <Badge variant="outline" className="gap-1">
                    {sourceConfig[selectedNewsletter.source].icon}
                    {sourceConfig[selectedNewsletter.source].label}
                  </Badge>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">Status:</span>
                  <Badge variant={statusConfig[selectedNewsletter.status].variant} className="gap-1">
                    {statusConfig[selectedNewsletter.status].icon}
                    {statusConfig[selectedNewsletter.status].label}
                  </Badge>
                </div>
                {selectedNewsletter.published_date && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground">Published:</span>
                    <span>{formatDistanceToNow(new Date(selectedNewsletter.published_date), { addSuffix: true })}</span>
                  </div>
                )}
              </div>

              {/* Content */}
              <div className="border rounded-lg">
                <ScrollArea className="h-[400px]">
                  <div className="p-4">
                    {selectedNewsletter.raw_text ? (
                      <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                        {selectedNewsletter.raw_text}
                      </pre>
                    ) : selectedNewsletter.raw_html ? (
                      <div
                        className="prose prose-sm max-w-none dark:prose-invert"
                        dangerouslySetInnerHTML={{ __html: selectedNewsletter.raw_html }}
                      />
                    ) : (
                      <p className="text-muted-foreground italic">No content available</p>
                    )}
                  </div>
                </ScrollArea>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2">
                {selectedNewsletter.url && (
                  <Button variant="outline" asChild>
                    <a
                      href={selectedNewsletter.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink className="mr-2 h-4 w-4" />
                      View Original
                    </a>
                  </Button>
                )}
                {selectedNewsletter.status === "completed" && (
                  <Button asChild>
                    <Link
                      to="/review/summary/$id"
                      params={{ id: String(selectedNewsletter.id) }}
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
              <p className="text-muted-foreground">Newsletter not found</p>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Ingest newsletters dialog */}
      <IngestNewslettersDialog
        open={ingestDialogOpen}
        onOpenChange={setIngestDialogOpen}
        onIngest={handleIngest}
        isIngesting={ingestMutation.isPending}
      />
    </PageContainer>
  )
}
