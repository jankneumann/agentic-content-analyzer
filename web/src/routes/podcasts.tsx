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
  useApprovedScripts,
  useGenerateAudio,
} from "@/hooks"
import { getAudioUrl } from "@/lib/api/podcasts"
import type { PodcastListItem } from "@/types"

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

function PodcastsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [selectedPodcastId, setSelectedPodcastId] = useState<number | null>(null)
  const [showGenerateDialog, setShowGenerateDialog] = useState(false)
  const [selectedScriptId, setSelectedScriptId] = useState<number | null>(null)

  const { data: podcasts, isLoading, isError, error, refetch } = usePodcasts(
    statusFilter === "all" ? undefined : { status: statusFilter }
  )
  const { data: stats } = usePodcastStats()
  const { data: selectedPodcast, isLoading: isLoadingPodcast } = usePodcast(
    selectedPodcastId ?? 0,
    { enabled: !!selectedPodcastId }
  )
  const { data: approvedScripts } = useApprovedScripts()
  const generateMutation = useGenerateAudio()

  const handleGenerateAudio = () => {
    if (!selectedScriptId) return

    generateMutation.mutate(
      {
        script_id: selectedScriptId,
        voice_provider: "openai_tts",
        alex_voice: "alex_male",
        sam_voice: "sam_female",
      },
      {
        onSuccess: () => {
          setShowGenerateDialog(false)
          setSelectedScriptId(null)
          refetch()
        },
      }
    )
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
            <Select value={statusFilter} onValueChange={setStatusFilter}>
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
                  <TableHead className="w-[100px]">Duration</TableHead>
                  <TableHead className="w-[100px]">Size</TableHead>
                  <TableHead className="w-[120px]">Provider</TableHead>
                  <TableHead className="w-[120px]">Status</TableHead>
                  <TableHead className="w-[130px]">Created</TableHead>
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
      <Dialog open={showGenerateDialog} onOpenChange={setShowGenerateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate Audio</DialogTitle>
            <DialogDescription>
              Select an approved script to generate podcast audio
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {!approvedScripts?.length ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No approved scripts available. Approve a script first.
              </p>
            ) : (
              <div className="space-y-2">
                <label className="text-sm font-medium">Select Script</label>
                <Select
                  value={selectedScriptId?.toString() ?? ""}
                  onValueChange={(v) => setSelectedScriptId(Number(v))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a script..." />
                  </SelectTrigger>
                  <SelectContent>
                    {approvedScripts.map((script) => (
                      <SelectItem key={script.id} value={script.id.toString()}>
                        {script.title ?? `Script #${script.id}`} ({script.length})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedScriptId && (
                  <div className="mt-4 p-3 rounded-lg border text-sm">
                    {(() => {
                      const script = approvedScripts.find((s) => s.id === selectedScriptId)
                      return script ? (
                        <>
                          <div>
                            <span className="text-muted-foreground">Length:</span>{" "}
                            <span className="font-medium capitalize">{script.length}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Words:</span>{" "}
                            <span className="font-medium">{script.word_count}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Est. Duration:</span>{" "}
                            <span className="font-medium">
                              {formatDuration(script.estimated_duration_seconds)}
                            </span>
                          </div>
                        </>
                      ) : null
                    })()}
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowGenerateDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleGenerateAudio}
              disabled={!selectedScriptId || generateMutation.isPending}
            >
              {generateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
          <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
            <a href={getAudioUrl(podcast.id)} download onClick={(e) => e.stopPropagation()}>
              <Download className="h-4 w-4" />
            </a>
          </Button>
        )}
      </TableCell>
    </TableRow>
  )
}
