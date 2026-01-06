/**
 * Newsletters Page
 *
 * Displays a list of ingested newsletters with filtering and search.
 * Allows triggering new ingestion from Gmail or RSS feeds.
 *
 * Route: /newsletters
 */

import { useState } from "react"
import { createRoute } from "@tanstack/react-router"
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
  DialogTrigger,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { useNewsletters, useIngestNewsletters, useNewsletterStats } from "@/hooks"
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
  const [selectedSource, setSelectedSource] = useState<NewsletterSource>("gmail")

  const { data, isLoading, isError, error, refetch } = useNewsletters(filters)
  const { data: stats } = useNewsletterStats()
  const ingestMutation = useIngestNewsletters()

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

  const handleIngest = () => {
    ingestMutation.mutate(
      { source: selectedSource },
      {
        onSuccess: () => {
          setIngestDialogOpen(false)
          refetch()
        },
      }
    )
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
          <Dialog open={ingestDialogOpen} onOpenChange={setIngestDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Ingest New
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Ingest Newsletters</DialogTitle>
                <DialogDescription>
                  Fetch new newsletters from Gmail or RSS feeds.
                </DialogDescription>
              </DialogHeader>
              <div className="py-4">
                <label className="text-sm font-medium">Source</label>
                <Select
                  value={selectedSource}
                  onValueChange={(v) => setSelectedSource(v as NewsletterSource)}
                >
                  <SelectTrigger className="mt-2">
                    <SelectValue placeholder="Select source" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gmail">
                      <div className="flex items-center gap-2">
                        <Mail className="h-4 w-4" />
                        Gmail
                      </div>
                    </SelectItem>
                    <SelectItem value="rss">
                      <div className="flex items-center gap-2">
                        <Rss className="h-4 w-4" />
                        RSS Feeds
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>

                {ingestMutation.isPending && (
                  <div className="mt-4 flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">
                      Ingesting newsletters...
                    </span>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setIngestDialogOpen(false)}
                  disabled={ingestMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleIngest}
                  disabled={ingestMutation.isPending}
                >
                  {ingestMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Ingesting...
                    </>
                  ) : (
                    <>
                      <Plus className="mr-2 h-4 w-4" />
                      Start Ingestion
                    </>
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
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
    </PageContainer>
  )
}
