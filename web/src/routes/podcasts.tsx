/**
 * Podcasts Page
 *
 * Displays generated audio podcasts with playback controls.
 * Allows triggering new audio generation from approved scripts.
 *
 * Route: /podcasts
 */

import { useState, useRef } from "react"
import { createRoute } from "@tanstack/react-router"
import {
  Radio,
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
  usePodcasts,
  usePodcastStats,
  usePodcast,
  useGenerateAudio,
  useScripts,
} from "@/hooks"
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext"
import {
  GenerateAudioDialog,
  type AudioGenerationParams,
} from "@/components/generation"
import { getAudioUrl } from "@/lib/api/podcasts"
import type { PodcastListItem, ScriptListItem, SortOrder } from "@/types"

export const PodcastsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "podcasts",
  component: PodcastsPage,
})

/**
 * Status badge configuration
 */
const statusConfig: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  generating: {
    label: "Generating",
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

interface PodcastFilters {
  status?: string
  sort_by?: string
  sort_order?: SortOrder
  offset?: number
}

function PodcastsPage() {
  const [filters, setFilters] = useState<PodcastFilters>({})
  const [selectedPodcastId, setSelectedPodcastId] = useState<number | null>(null)
  const [showGenerateDialog, setShowGenerateDialog] = useState(false)

  const handleSort = (column: string, order: SortOrder | undefined) => {
    setFilters((prev) => ({
      ...prev,
      sort_by: order ? column : undefined,
      sort_order: order,
      offset: 0,
    }))
  }

  const { data: podcasts, isLoading, isError, error, refetch } = usePodcasts(
    filters.status || filters.sort_by
      ? {
          status: filters.status,
          sort_by: filters.sort_by,
          sort_order: filters.sort_order,
        }
      : undefined
  )
  const { data: stats } = usePodcastStats()
  const { data: selectedPodcast, isLoading: isLoadingPodcast } = usePodcast(
    selectedPodcastId ?? 0,
    { enabled: !!selectedPodcastId }
  )
  const { data: scripts } = useScripts({ status: "script_approved" })
  const generateMutation = useGenerateAudio()
  const { addTask, updateTask, completeTask, failTask } = useBackgroundTasks()

  const handleGenerateAudio = (params: AudioGenerationParams) => {
    // Close dialog immediately - task runs in background
    setShowGenerateDialog(false)

    // Add background task
    const taskId = addTask({
      type: "audio",
      title: "Generate Podcast Audio",
      message: "Starting audio generation...",
    })

    generateMutation.mutate(
      {
        script_id: params.script_id,
        voice_provider: params.voice_provider,
        alex_voice: params.alex_voice,
        sam_voice: params.sam_voice,
      },
      {
        onSuccess: () => {
          // API returns "queued" - actual work happens in background
          // Poll for completion by checking podcast list
          updateTask(taskId, { progress: 20, message: "Processing script sections..." })

          let pollCount = 0
          const maxPolls = 120 // 10 minutes max (5s intervals) - audio gen is slow

          const pollInterval = setInterval(async () => {
            pollCount++
            const progressPercent = Math.min(20 + pollCount * 0.6, 95)
            updateTask(taskId, {
              progress: Math.round(progressPercent),
              message:
                pollCount < 15
                  ? "Processing script sections..."
                  : pollCount < 30
                    ? "Generating audio segments..."
                    : pollCount < 60
                      ? "Synthesizing voices..."
                      : pollCount < 90
                        ? "Combining audio tracks..."
                        : "Encoding final audio...",
            })

            const result = await refetch()
            // Look for a podcast that just completed or is generating for this script
            const newPodcast = result.data?.find(
              (p) => p.script_id === params.script_id && p.status === "completed"
            )
            const generatingPodcast = result.data?.find(
              (p) => p.script_id === params.script_id && p.status === "generating"
            )
            const failedPodcast = result.data?.find(
              (p) => p.script_id === params.script_id && p.status === "failed"
            )

            if (newPodcast || failedPodcast || pollCount >= maxPolls) {
              clearInterval(pollInterval)
              if (newPodcast) {
                completeTask(taskId, "Audio generated successfully")
                toast.success("Podcast audio generated")
              } else if (failedPodcast) {
                failTask(taskId, failedPodcast.error_message ?? "Audio generation failed")
                toast.error(`Audio generation failed: ${failedPodcast.error_message}`)
              } else if (!generatingPodcast) {
                // No generating podcast found after timeout
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

  return (
    <PageContainer
      title="Podcasts"
      description="Generated audio podcasts with playback and download"
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button onClick={() => setShowGenerateDialog(true)}>
            <Play className="mr-2 h-4 w-4" />
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
              <CardDescription>Generating</CardDescription>
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

      {/* Podcast list */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Radio className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Podcast List</CardTitle>
          </div>
          <CardDescription>
            {podcasts?.length ?? 0} podcasts
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
                <SelectItem value="generating">Generating</SelectItem>
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
                  Error loading podcasts: {error?.message}
                </p>
                <Button className="mt-4" size="sm" onClick={() => refetch()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Retry
                </Button>
              </div>
            </div>
          ) : !podcasts?.length ? (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
              <div className="text-center">
                <Radio className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  No podcasts generated yet
                </p>
                <p className="text-xs text-muted-foreground">
                  Approve a script and generate audio to create a podcast
                </p>
                <Button
                  className="mt-4"
                  size="sm"
                  onClick={() => setShowGenerateDialog(true)}
                >
                  <Play className="mr-2 h-4 w-4" />
                  Generate Audio
                </Button>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
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
                  <TableHead className="w-[120px]">Provider</TableHead>
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
                  <TableHead className="w-[80px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {podcasts.map((podcast) => (
                  <PodcastRow
                    key={podcast.id}
                    podcast={podcast}
                    onView={() => setSelectedPodcastId(podcast.id)}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Podcast player dialog */}
      <Dialog
        open={!!selectedPodcastId}
        onOpenChange={(open) => !open && setSelectedPodcastId(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedPodcast?.title ?? "Podcast Player"}</DialogTitle>
            <DialogDescription>
              {selectedPodcast?.length} podcast
              {selectedPodcast?.duration_seconds && (
                <> - {formatDuration(selectedPodcast.duration_seconds)}</>
              )}
            </DialogDescription>
          </DialogHeader>
          {isLoadingPodcast ? (
            <div className="space-y-4 py-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : selectedPodcast ? (
            <div className="space-y-6 py-4">
              {/* Audio Player */}
              {selectedPodcast.status === "completed" ? (
                <AudioPlayer
                  podcastId={selectedPodcast.id}
                  duration={selectedPodcast.duration_seconds}
                />
              ) : selectedPodcast.status === "generating" ? (
                <div className="flex items-center justify-center gap-2 py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                  <span>Audio is being generated...</span>
                </div>
              ) : (
                <div className="flex items-center justify-center gap-2 py-8 text-destructive">
                  <AlertCircle className="h-6 w-6" />
                  <span>Audio generation failed: {selectedPodcast.error_message}</span>
                </div>
              )}

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Script ID:</span>{" "}
                  <span className="font-medium">{selectedPodcast.script_id}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Digest ID:</span>{" "}
                  <span className="font-medium">{selectedPodcast.digest_id}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Voice Provider:</span>{" "}
                  <span className="font-medium">{selectedPodcast.voice_provider}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Format:</span>{" "}
                  <span className="font-medium">{selectedPodcast.audio_format}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">File Size:</span>{" "}
                  <span className="font-medium">{formatFileSize(selectedPodcast.file_size_bytes)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Word Count:</span>{" "}
                  <span className="font-medium">{selectedPodcast.word_count ?? "N/A"}</span>
                </div>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedPodcastId(null)}>
              Close
            </Button>
            {selectedPodcast?.status === "completed" && (
              <Button asChild>
                <a href={getAudioUrl(selectedPodcast.id)} download>
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </a>
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Generate audio dialog */}
      <GenerateAudioDialog
        open={showGenerateDialog}
        onOpenChange={setShowGenerateDialog}
        onGenerate={handleGenerateAudio}
        isGenerating={generateMutation.isPending}
        scripts={scripts as ScriptListItem[] | undefined}
      />
    </PageContainer>
  )
}

/**
 * Audio Player Component
 */
function AudioPlayer({
  podcastId,
  duration,
}: {
  podcastId: number
  duration: number | null
}) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1.0)

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

  const handlePlaybackRateChange = (rate: string) => {
    const newRate = parseFloat(rate)
    setPlaybackRate(newRate)
    if (audioRef.current) {
      audioRef.current.playbackRate = newRate
    }
  }

  const totalDuration = duration ?? 0

  // Common playback speeds
  const playbackSpeeds = [
    { value: "0.5", label: "0.5x" },
    { value: "0.75", label: "0.75x" },
    { value: "1", label: "1x" },
    { value: "1.25", label: "1.25x" },
    { value: "1.5", label: "1.5x" },
    { value: "1.75", label: "1.75x" },
    { value: "2", label: "2x" },
  ]

  return (
    <div className="space-y-4 p-4 rounded-lg border bg-muted/30">
      <audio
        ref={audioRef}
        src={getAudioUrl(podcastId)}
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
          <Button
            variant="ghost"
            size="icon"
            onClick={() => skip(-10)}
            aria-label="Rewind 10 seconds"
          >
            <SkipBack className="h-4 w-4" />
          </Button>
          <Button
            size="icon"
            onClick={togglePlay}
            aria-label={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? (
              <Pause className="h-5 w-5" />
            ) : (
              <Play className="h-5 w-5" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => skip(10)}
            aria-label="Forward 10 seconds"
          >
            <SkipForward className="h-4 w-4" />
          </Button>
        </div>

        {/* Speed & Volume */}
        <div className="flex items-center gap-4">
          {/* Playback Speed */}
          <Select value={String(playbackRate)} onValueChange={handlePlaybackRateChange}>
            <SelectTrigger className="w-20 h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {playbackSpeeds.map((speed) => (
                <SelectItem key={speed.value} value={speed.value}>
                  {speed.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Volume */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleMute}
              aria-label={isMuted ? "Unmute" : "Mute"}
            >
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
    </div>
  )
}

/**
 * Podcast row component
 */
function PodcastRow({
  podcast,
  onView,
}: {
  podcast: PodcastListItem
  onView: () => void
}) {
  const status = statusConfig[podcast.status] ?? {
    label: podcast.status,
    variant: "outline" as const,
    icon: null,
  }

  return (
    <TableRow className="cursor-pointer hover:bg-muted/50" onClick={onView}>
      <TableCell>
        <div>
          <div className="font-medium line-clamp-1">
            {podcast.title ?? `Podcast #${podcast.id}`}
          </div>
          <div className="text-sm text-muted-foreground">
            Script #{podcast.script_id}
          </div>
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {formatDuration(podcast.duration_seconds)}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {formatFileSize(podcast.file_size_bytes)}
        </span>
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="capitalize">
          {podcast.voice_provider ?? "unknown"}
        </Badge>
      </TableCell>
      <TableCell>
        <Badge variant={status.variant} className="gap-1">
          {status.icon}
          {status.label}
        </Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {podcast.created_at
            ? formatDistanceToNow(new Date(podcast.created_at), { addSuffix: true })
            : "Unknown"}
        </span>
      </TableCell>
      <TableCell>
        {podcast.status === "completed" && (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            asChild
            aria-label="Download audio"
          >
            <a
              href={getAudioUrl(podcast.id)}
              download
              onClick={(e) => e.stopPropagation()}
            >
              <Download className="h-4 w-4" />
            </a>
          </Button>
        )}
      </TableCell>
    </TableRow>
  )
}
