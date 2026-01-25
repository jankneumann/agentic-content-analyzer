/**
 * Audio Digests Page
 *
 * Displays generated audio digests with playback controls.
 * Allows triggering new audio generation from completed digests.
 *
 * Unlike podcasts (dual-voice dialogue), audio digests are single-voice
 * TTS narrations of digest content.
 *
 * Route: /audio-digests
 */

import { useState, useRef } from "react"
import { createRoute } from "@tanstack/react-router"
import {
  Headphones,
  Play,
  Pause,
  RefreshCw,
  Download,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  Volume2,
  VolumeX,
  SkipBack,
  SkipForward,
  Trash2,
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
import { Slider } from "@/components/ui/slider"
import {
  useAudioDigests,
  useAudioDigestStats,
  useAudioDigest,
  useAvailableDigests,
  useCreateAudioDigest,
  useDeleteAudioDigest,
} from "@/hooks"
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext"
import {
  GenerateAudioDigestDialog,
  type AudioDigestGenerationParams,
} from "@/components/generation/GenerateAudioDigestDialog"
import { getAudioDigestUrl } from "@/lib/api/audio-digests"
import type { AudioDigestListItem, AudioDigestFilters as AudioDigestApiFilters, SortOrder } from "@/types"

export const AudioDigestsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "audio-digests",
  component: AudioDigestsPage,
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
    variant: "outline",
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
 * Format duration in seconds to mm:ss
 */
function formatDuration(seconds: number | null): string {
  if (!seconds) return "--:--"
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

/**
 * Format file size in bytes to human readable
 */
function formatFileSize(bytes: number | null): string {
  if (!bytes) return "Unknown"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface AudioDigestFilters {
  status?: string
  sort_by?: string
  sort_order?: SortOrder
  offset?: number
}

function AudioDigestsPage() {
  const [filters, setFilters] = useState<AudioDigestFilters>({})
  const [selectedAudioDigestId, setSelectedAudioDigestId] = useState<number | null>(null)
  const [showGenerateDialog, setShowGenerateDialog] = useState(false)
  const [audioDigestToDelete, setAudioDigestToDelete] = useState<AudioDigestListItem | null>(null)

  const handleSort = (column: string, order: SortOrder | undefined) => {
    setFilters((prev) => ({
      ...prev,
      sort_by: order ? column : undefined,
      sort_order: order,
      offset: 0,
    }))
  }

  const { data: audioDigests, isLoading, isError, error, refetch } = useAudioDigests(
    filters.status || filters.sort_by
      ? {
          status: filters.status as AudioDigestApiFilters["status"],
          sort_by: filters.sort_by,
          sort_order: filters.sort_order,
        }
      : undefined
  )
  const { data: stats } = useAudioDigestStats()
  const { data: selectedAudioDigest, isLoading: isLoadingAudioDigest } = useAudioDigest(
    selectedAudioDigestId ?? 0,
    { enabled: !!selectedAudioDigestId }
  )
  const { data: availableDigests } = useAvailableDigests()
  const createMutation = useCreateAudioDigest()
  const deleteMutation = useDeleteAudioDigest()
  const { addTask, updateTask, completeTask, failTask } = useBackgroundTasks()

  const handleGenerateAudio = (params: AudioDigestGenerationParams) => {
    // Close dialog immediately - task runs in background
    setShowGenerateDialog(false)

    // Add background task
    const taskId = addTask({
      type: "audio",
      title: "Generate Audio Digest",
      message: "Starting audio generation...",
    })

    createMutation.mutate(
      {
        digestId: params.digest_id,
        request: {
          voice: params.voice,
          speed: params.speed,
          provider: params.provider,
        },
      },
      {
        onSuccess: () => {
          // API returns "pending" - actual work happens in background
          // Poll for completion by checking audio digest list
          updateTask(taskId, { progress: 20, message: "Processing digest content..." })

          let pollCount = 0
          const maxPolls = 120 // 10 minutes max (5s intervals) - audio gen is slow

          const pollInterval = setInterval(async () => {
            pollCount++
            const progressPercent = Math.min(20 + pollCount * 0.6, 95)
            updateTask(taskId, {
              progress: Math.round(progressPercent),
              message:
                pollCount < 15
                  ? "Processing digest content..."
                  : pollCount < 30
                    ? "Chunking text for TTS..."
                    : pollCount < 60
                      ? "Synthesizing audio..."
                      : pollCount < 90
                        ? "Combining audio segments..."
                        : "Finalizing audio...",
            })

            const result = await refetch()
            // Look for an audio digest that just completed or is processing for this digest
            const newAudioDigest = result.data?.find(
              (a) => a.digest_id === params.digest_id && a.status === "completed"
            )
            const processingAudioDigest = result.data?.find(
              (a) => a.digest_id === params.digest_id && (a.status === "processing" || a.status === "pending")
            )
            const failedAudioDigest = result.data?.find(
              (a) => a.digest_id === params.digest_id && a.status === "failed"
            )

            if (newAudioDigest || failedAudioDigest || pollCount >= maxPolls) {
              clearInterval(pollInterval)
              if (newAudioDigest) {
                completeTask(taskId, "Audio digest generated successfully")
                toast.success("Audio digest generated")
              } else if (failedAudioDigest) {
                failTask(taskId, failedAudioDigest.error_message ?? "Audio generation failed")
                toast.error(`Audio generation failed: ${failedAudioDigest.error_message}`)
              } else if (!processingAudioDigest) {
                // No processing audio digest found after timeout
                updateTask(taskId, { progress: 95, message: "Generation may still be in progress..." })
              }
            }
          }, 5000)
        },
        onError: (err) => {
          const errorMsg = err instanceof Error ? err.message : "Unknown error"
          failTask(taskId, errorMsg)
          toast.error(`Failed to generate audio: ${errorMsg}`)
        },
      }
    )

    // Update progress indicator
    updateTask(taskId, { progress: 10, message: "Queuing audio generation..." })
  }

  const handleDelete = (audioDigest: AudioDigestListItem) => {
    setAudioDigestToDelete(audioDigest)
  }

  const confirmDelete = () => {
    if (!audioDigestToDelete) return

    deleteMutation.mutate(audioDigestToDelete.id, {
      onSuccess: () => {
        toast.success("Audio digest deleted")
        setAudioDigestToDelete(null)
        refetch()
      },
      onError: (err) => {
        const errorMsg = err instanceof Error ? err.message : "Unknown error"
        toast.error(`Failed to delete: ${errorMsg}`)
      },
    })
  }

  return (
    <PageContainer
      title="Audio Digests"
      description="Single-voice TTS audio from digest content"
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button onClick={() => setShowGenerateDialog(true)}>
            <Headphones className="mr-2 h-4 w-4" />
            Generate Audio
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
              <CardDescription>Processing</CardDescription>
              <CardTitle className="text-2xl">{stats.generating}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Completed</CardDescription>
              <CardTitle className="text-2xl">{stats.completed}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Duration</CardDescription>
              <CardTitle className="text-2xl">
                {formatDuration(stats.total_duration_seconds)}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Audio digest list */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Headphones className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Audio Digest List</CardTitle>
          </div>
          <CardDescription>
            {audioDigests?.length ?? 0} audio digests
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filter row */}
          <div className="mb-4 flex gap-4">
            <Select
              value={filters.status ?? "all"}
              onValueChange={(value) =>
                setFilters((prev) => ({
                  ...prev,
                  status: value === "all" ? undefined : value,
                  offset: 0,
                }))
              }
            >
              <SelectTrigger className="w-[180px]">
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
                  Error loading audio digests: {error?.message}
                </p>
                <Button className="mt-4" size="sm" onClick={() => refetch()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Retry
                </Button>
              </div>
            </div>
          ) : !audioDigests?.length ? (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
              <div className="text-center">
                <Headphones className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  No audio digests generated yet
                </p>
                <p className="text-xs text-muted-foreground">
                  Select a completed digest and generate audio
                </p>
                <Button
                  className="mt-4"
                  size="sm"
                  onClick={() => setShowGenerateDialog(true)}
                >
                  <Headphones className="mr-2 h-4 w-4" />
                  Generate Audio
                </Button>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source Digest</TableHead>
                  <SortableTableHead
                    column="duration_seconds"
                    label="Duration"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[100px]"
                  />
                  <SortableTableHead
                    column="file_size_bytes"
                    label="Size"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[100px]"
                  />
                  <TableHead className="w-[100px]">Voice</TableHead>
                  <TableHead className="w-[100px]">Speed</TableHead>
                  <SortableTableHead
                    column="status"
                    label="Status"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[120px]"
                  />
                  <SortableTableHead
                    column="created_at"
                    label="Created"
                    currentSort={filters.sort_by}
                    currentOrder={filters.sort_order}
                    onSort={handleSort}
                    className="w-[130px]"
                  />
                  <TableHead className="w-[100px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {audioDigests.map((audioDigest) => (
                  <AudioDigestRow
                    key={audioDigest.id}
                    audioDigest={audioDigest}
                    onView={() => setSelectedAudioDigestId(audioDigest.id)}
                    onDelete={() => handleDelete(audioDigest)}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Audio player dialog */}
      <Dialog
        open={!!selectedAudioDigestId}
        onOpenChange={(open) => !open && setSelectedAudioDigestId(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Audio Digest Player</DialogTitle>
            <DialogDescription>
              Digest #{selectedAudioDigest?.digest_id}
              {selectedAudioDigest?.duration_seconds && (
                <> - {formatDuration(selectedAudioDigest.duration_seconds)}</>
              )}
            </DialogDescription>
          </DialogHeader>
          {isLoadingAudioDigest ? (
            <div className="space-y-4 py-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : selectedAudioDigest ? (
            <div className="space-y-6 py-4">
              {/* Audio Player */}
              {selectedAudioDigest.status === "completed" ? (
                <AudioPlayer
                  audioDigestId={selectedAudioDigest.id}
                  duration={selectedAudioDigest.duration_seconds}
                />
              ) : selectedAudioDigest.status === "processing" || selectedAudioDigest.status === "pending" ? (
                <div className="flex items-center justify-center gap-2 py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                  <span>Audio is being generated...</span>
                </div>
              ) : (
                <div className="flex items-center justify-center gap-2 py-8 text-destructive">
                  <AlertCircle className="h-6 w-6" />
                  <span>Audio generation failed: {selectedAudioDigest.error_message}</span>
                </div>
              )}

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Digest ID:</span>{" "}
                  <span className="font-medium">{selectedAudioDigest.digest_id}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Voice:</span>{" "}
                  <span className="font-medium capitalize">{selectedAudioDigest.voice}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Speed:</span>{" "}
                  <span className="font-medium">{selectedAudioDigest.speed}x</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Provider:</span>{" "}
                  <span className="font-medium capitalize">{selectedAudioDigest.provider}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">File Size:</span>{" "}
                  <span className="font-medium">{formatFileSize(selectedAudioDigest.file_size_bytes)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Format:</span>{" "}
                  <span className="font-medium">{selectedAudioDigest.audio_format}</span>
                </div>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedAudioDigestId(null)}>
              Close
            </Button>
            {selectedAudioDigest?.status === "completed" && (
              <Button asChild>
                <a href={getAudioDigestUrl(selectedAudioDigest.id)} download>
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </a>
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!audioDigestToDelete}
        onOpenChange={(open: boolean) => !open && setAudioDigestToDelete(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Audio Digest?</DialogTitle>
            <DialogDescription>
              This will permanently delete this audio digest. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAudioDigestToDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Generate audio dialog */}
      <GenerateAudioDigestDialog
        open={showGenerateDialog}
        onOpenChange={setShowGenerateDialog}
        onGenerate={handleGenerateAudio}
        isGenerating={createMutation.isPending}
        digests={availableDigests}
      />
    </PageContainer>
  )
}

/**
 * Audio Player Component
 */
function AudioPlayer({
  audioDigestId,
  duration,
}: {
  audioDigestId: number
  duration: number | null
}) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause()
      } else {
        audioRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime)
    }
  }

  const handleSeek = (value: number[]) => {
    if (audioRef.current) {
      audioRef.current.currentTime = value[0]
      setCurrentTime(value[0])
    }
  }

  const handleVolumeChange = (value: number[]) => {
    const newVolume = value[0]
    setVolume(newVolume)
    if (audioRef.current) {
      audioRef.current.volume = newVolume
    }
    setIsMuted(newVolume === 0)
  }

  const toggleMute = () => {
    if (audioRef.current) {
      if (isMuted) {
        audioRef.current.volume = volume || 1
        setIsMuted(false)
      } else {
        audioRef.current.volume = 0
        setIsMuted(true)
      }
    }
  }

  const skip = (seconds: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime += seconds
    }
  }

  const totalDuration = duration ?? 0

  return (
    <div className="space-y-4 p-4 rounded-lg border bg-muted/30">
      <audio
        ref={audioRef}
        src={getAudioDigestUrl(audioDigestId)}
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => setIsPlaying(false)}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />

      {/* Progress bar */}
      <div className="space-y-2">
        <Slider
          value={[currentTime]}
          max={totalDuration}
          step={1}
          onValueChange={handleSeek}
          className="cursor-pointer"
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{formatDuration(currentTime)}</span>
          <span>{formatDuration(totalDuration)}</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => skip(-10)}>
            <SkipBack className="h-4 w-4" />
          </Button>
          <Button size="icon" onClick={togglePlay}>
            {isPlaying ? (
              <Pause className="h-5 w-5" />
            ) : (
              <Play className="h-5 w-5" />
            )}
          </Button>
          <Button variant="ghost" size="icon" onClick={() => skip(10)}>
            <SkipForward className="h-4 w-4" />
          </Button>
        </div>

        {/* Volume */}
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={toggleMute}>
            {isMuted ? (
              <VolumeX className="h-4 w-4" />
            ) : (
              <Volume2 className="h-4 w-4" />
            )}
          </Button>
          <Slider
            value={[isMuted ? 0 : volume]}
            max={1}
            step={0.1}
            onValueChange={handleVolumeChange}
            className="w-24"
          />
        </div>
      </div>
    </div>
  )
}

/**
 * Audio digest row component
 */
function AudioDigestRow({
  audioDigest,
  onView,
  onDelete,
}: {
  audioDigest: AudioDigestListItem
  onView: () => void
  onDelete: () => void
}) {
  const status = statusConfig[audioDigest.status] ?? {
    label: audioDigest.status,
    variant: "outline" as const,
    icon: null,
  }

  return (
    <TableRow className="cursor-pointer hover:bg-muted/50" onClick={onView}>
      <TableCell>
        <div>
          <div className="font-medium">
            Digest #{audioDigest.digest_id}
          </div>
          <div className="text-sm text-muted-foreground">
            Audio #{audioDigest.id}
          </div>
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {formatDuration(audioDigest.duration_seconds)}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {formatFileSize(audioDigest.file_size_bytes)}
        </span>
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="capitalize">
          {audioDigest.voice}
        </Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {audioDigest.speed}x
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
          {audioDigest.created_at
            ? formatDistanceToNow(new Date(audioDigest.created_at), { addSuffix: true })
            : "Unknown"}
        </span>
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-1">
          {audioDigest.status === "completed" && (
            <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
              <a href={getAudioDigestUrl(audioDigest.id)} download onClick={(e) => e.stopPropagation()}>
                <Download className="h-4 w-4" />
              </a>
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-destructive hover:text-destructive"
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}
