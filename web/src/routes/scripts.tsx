/**
 * Scripts Page
 *
 * Displays podcast scripts with review workflow.
 * Scripts are generated from digests and can be reviewed/approved.
 *
 * Route: /scripts
 */

import { useState } from "react"
import { createRoute } from "@tanstack/react-router"
import {
  FileText,
  Play,
  RefreshCw,
  Search,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  Eye,
  ThumbsUp,
  ThumbsDown,
  Edit3,
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
import { useScripts, useScriptStats, useScript, useApproveScript, useRejectScript } from "@/hooks"
import type { ScriptListItem } from "@/types"

/**
 * Script detail type for display
 */
interface ScriptDetailSection {
  section_type: string
  title: string
  dialogue: unknown[]
}

interface ScriptDetail {
  title?: string
  length?: string
  status?: string
  sections?: ScriptDetailSection[]
}

export const ScriptsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "scripts",
  component: ScriptsPage,
})

/**
 * Status badge configuration
 */
const statusConfig: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  pending: {
    label: "Pending",
    variant: "secondary",
    icon: <Clock className="h-3 w-3" />,
  },
  script_generating: {
    label: "Generating",
    variant: "outline",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  script_pending_review: {
    label: "Pending Review",
    variant: "secondary",
    icon: <Eye className="h-3 w-3" />,
  },
  script_revision_requested: {
    label: "Revision Requested",
    variant: "outline",
    icon: <Edit3 className="h-3 w-3" />,
  },
  script_approved: {
    label: "Approved",
    variant: "default",
    icon: <CheckCircle className="h-3 w-3" />,
  },
  audio_generating: {
    label: "Audio Generating",
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

function ScriptsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [searchValue, setSearchValue] = useState("")
  const [selectedScriptId, setSelectedScriptId] = useState<number | null>(null)

  const { data: scripts, isLoading, isError, error, refetch } = useScripts(
    statusFilter === "all" ? undefined : { status: statusFilter }
  )
  const { data: stats } = useScriptStats()
  const { data: selectedScript, isLoading: isLoadingScript } = useScript(
    selectedScriptId ?? 0,
    { enabled: !!selectedScriptId }
  )
  const approveMutation = useApproveScript()
  const rejectMutation = useRejectScript()

  const handleApprove = (scriptId: number) => {
    approveMutation.mutate(
      { scriptId, reviewer: "user" },
      {
        onSuccess: () => {
          setSelectedScriptId(null)
          refetch()
        },
      }
    )
  }

  const handleReject = (scriptId: number) => {
    rejectMutation.mutate(
      { scriptId, reviewer: "user", reason: "Rejected via UI" },
      {
        onSuccess: () => {
          setSelectedScriptId(null)
          refetch()
        },
      }
    )
  }

  // Filter scripts by search
  const filteredScripts = scripts?.filter((script) => {
    if (!searchValue) return true
    return script.title?.toLowerCase().includes(searchValue.toLowerCase())
  })

  return (
    <PageContainer
      title="Scripts"
      description="Podcast scripts generated from digests with review workflow"
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button disabled>
            <Play className="mr-2 h-4 w-4" />
            Generate Script
          </Button>
        </div>
      }
    >
      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
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
              <CardDescription>Revision Requested</CardDescription>
              <CardTitle className="text-2xl">{stats.revision_requested}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Approved</CardDescription>
              <CardTitle className="text-2xl">{stats.approved_ready_for_audio}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Completed</CardDescription>
              <CardTitle className="text-2xl">{stats.completed_with_audio}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Script list */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Script List</CardTitle>
          </div>
          <CardDescription>
            {scripts?.length ?? 0} scripts
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filter row */}
          <div className="mb-4 flex flex-col gap-4 md:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search scripts..."
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={statusFilter}
              onValueChange={setStatusFilter}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="script_pending_review">Pending Review</SelectItem>
                <SelectItem value="script_revision_requested">Revision Requested</SelectItem>
                <SelectItem value="script_approved">Approved</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
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
                  Error loading scripts: {error?.message}
                </p>
                <Button className="mt-4" size="sm" onClick={() => refetch()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Retry
                </Button>
              </div>
            </div>
          ) : !filteredScripts?.length ? (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
              <div className="text-center">
                <FileText className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  No scripts found
                </p>
                <p className="text-xs text-muted-foreground">
                  Generate a script from an approved digest
                </p>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead className="w-[100px]">Length</TableHead>
                  <TableHead className="w-[100px]">Duration</TableHead>
                  <TableHead className="w-[150px]">Status</TableHead>
                  <TableHead className="w-[100px]">Revisions</TableHead>
                  <TableHead className="w-[130px]">Created</TableHead>
                  <TableHead className="w-[60px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredScripts.map((script) => (
                  <ScriptRow
                    key={script.id}
                    script={script}
                    onView={() => setSelectedScriptId(script.id)}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Script detail dialog */}
      <Dialog
        open={!!selectedScriptId}
        onOpenChange={(open) => !open && setSelectedScriptId(null)}
      >
        <DialogContent className="max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Script Details</DialogTitle>
            <DialogDescription>
              Review script content and approve or request revisions
            </DialogDescription>
          </DialogHeader>
          {isLoadingScript ? (
            <div className="space-y-4 py-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : selectedScript ? (
            (() => {
              const script = selectedScript as ScriptDetail
              return (
                <ScrollArea className="max-h-[60vh] pr-4">
                  <div className="space-y-6 py-4">
                    {/* Script metadata */}
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <span className="text-sm text-muted-foreground">Title:</span>{" "}
                        <span className="font-medium">{script.title ?? "Untitled"}</span>
                      </div>
                      <div>
                        <span className="text-sm text-muted-foreground">Length:</span>{" "}
                        <span className="font-medium">{script.length ?? ""}</span>
                      </div>
                      <div>
                        <span className="text-sm text-muted-foreground">Status:</span>{" "}
                        <Badge variant="secondary">
                          {script.status ?? ""}
                        </Badge>
                      </div>
                    </div>

                    {/* Sections preview */}
                    {script.sections && (
                      <div>
                        <h4 className="text-sm font-medium text-muted-foreground mb-2">
                          Sections
                        </h4>
                        <div className="space-y-2">
                          {script.sections.map((section, i) => (
                            <div key={i} className="p-3 rounded-lg border">
                              <div className="flex items-center gap-2 mb-1">
                                <Badge variant="outline" className="text-xs">
                                  {section.section_type}
                                </Badge>
                                <span className="font-medium text-sm">
                                  {section.title}
                                </span>
                              </div>
                              <p className="text-xs text-muted-foreground">
                                {section.dialogue?.length ?? 0} dialogue turns
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              )
            })()
          ) : null}
          <DialogFooter className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setSelectedScriptId(null)}
            >
              Close
            </Button>
            {selectedScriptId && (
              <>
                <Button
                  variant="destructive"
                  onClick={() => handleReject(selectedScriptId)}
                  disabled={rejectMutation.isPending}
                >
                  <ThumbsDown className="mr-2 h-4 w-4" />
                  Reject
                </Button>
                <Button
                  onClick={() => handleApprove(selectedScriptId)}
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
    </PageContainer>
  )
}

/**
 * Script row component
 */
function ScriptRow({
  script,
  onView,
}: {
  script: ScriptListItem
  onView: () => void
}) {
  const status = statusConfig[script.status] ?? {
    label: script.status,
    variant: "outline" as const,
    icon: null,
  }

  return (
    <TableRow className="cursor-pointer hover:bg-muted/50" onClick={onView}>
      <TableCell>
        <div>
          <div className="font-medium line-clamp-1">
            {script.title ?? `Script #${script.id}`}
          </div>
          <div className="text-sm text-muted-foreground">
            Digest #{script.digest_id}
          </div>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="capitalize">
          {script.length}
        </Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {script.estimated_duration ?? "?"}
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
          {script.revision_count}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {script.created_at
            ? formatDistanceToNow(new Date(script.created_at), { addSuffix: true })
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
