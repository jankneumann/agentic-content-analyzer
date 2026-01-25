/**
 * GenerateAudioDigestDialog Component
 *
 * Dialog for configuring and triggering audio digest generation.
 * Unlike podcast audio (dual voices), audio digests use a single voice
 * for TTS narration of digest content.
 *
 * Allows selecting:
 * - Source digest (completed/approved)
 * - Voice (single voice for narration)
 * - Speed (0.5x to 2.0x)
 * - Provider (OpenAI TTS, ElevenLabs)
 */

import * as React from "react"
import { Loader2, Headphones, Gauge } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import type { AvailableDigest, AudioDigestVoice, AudioDigestProvider } from "@/types"

interface GenerateAudioDigestDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onGenerate: (params: AudioDigestGenerationParams) => void
  isGenerating?: boolean
  digests?: AvailableDigest[]
  preselectedDigestId?: number
}

export interface AudioDigestGenerationParams {
  digest_id: number
  voice: AudioDigestVoice
  speed: number
  provider: AudioDigestProvider
}

const voiceProviders: { value: AudioDigestProvider; label: string }[] = [
  { value: "openai", label: "OpenAI TTS" },
  { value: "elevenlabs", label: "ElevenLabs" },
]

const voices: { value: AudioDigestVoice; label: string; description: string }[] = [
  { value: "nova", label: "Nova", description: "Warm Female" },
  { value: "onyx", label: "Onyx", description: "Deep Male" },
  { value: "echo", label: "Echo", description: "Natural Male" },
  { value: "shimmer", label: "Shimmer", description: "Expressive Female" },
  { value: "alloy", label: "Alloy", description: "Neutral" },
  { value: "fable", label: "Fable", description: "Storytelling" },
]

export function GenerateAudioDigestDialog({
  open,
  onOpenChange,
  onGenerate,
  isGenerating = false,
  digests = [],
  preselectedDigestId,
}: GenerateAudioDigestDialogProps) {
  // Form state
  const [digestId, setDigestId] = React.useState<number | null>(
    preselectedDigestId ?? null
  )
  const [voice, setVoice] = React.useState<AudioDigestVoice>("nova")
  const [speed, setSpeed] = React.useState(1.0)
  const [provider, setProvider] = React.useState<AudioDigestProvider>("openai")

  // Update digest ID when preselected changes
  React.useEffect(() => {
    if (preselectedDigestId) {
      setDigestId(preselectedDigestId)
    }
  }, [preselectedDigestId])

  // Reset form when dialog opens
  React.useEffect(() => {
    if (open && !preselectedDigestId) {
      setDigestId(null)
      setVoice("nova")
      setSpeed(1.0)
      setProvider("openai")
    }
  }, [open, preselectedDigestId])

  const handleGenerate = () => {
    if (!digestId) return

    onGenerate({
      digest_id: digestId,
      voice,
      speed,
      provider,
    })
  }

  const selectedDigest = digests.find((d) => d.id === digestId)
  const selectedVoice = voices.find((v) => v.value === voice)

  // Format speed for display
  const formatSpeed = (value: number) => `${value.toFixed(1)}x`

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Headphones className="h-5 w-5" />
            Generate Audio Digest
          </DialogTitle>
          <DialogDescription>
            Create a single-voice audio narration from a digest.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Source Digest */}
          <div className="space-y-2">
            <Label>Source Digest</Label>
            <Select
              value={digestId ? String(digestId) : ""}
              onValueChange={(v) => setDigestId(Number(v))}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a digest..." />
              </SelectTrigger>
              <SelectContent className="max-w-[calc(500px-3rem)]">
                {digests.length === 0 ? (
                  <SelectItem value="" disabled>
                    No completed digests available
                  </SelectItem>
                ) : (
                  digests.map((digest) => (
                    <SelectItem
                      key={digest.id}
                      value={String(digest.id)}
                      className="max-w-full"
                    >
                      <span className="truncate">
                        [{digest.id}] {digest.title ?? `Digest #${digest.id}`}
                      </span>
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
            {selectedDigest && (
              <p className="text-xs text-muted-foreground">
                {selectedDigest.digest_type} •{" "}
                {new Date(selectedDigest.created_at).toLocaleDateString()}
              </p>
            )}
          </div>

          {/* Voice Provider */}
          <div className="space-y-2">
            <Label>Voice Provider</Label>
            <Select
              value={provider}
              onValueChange={(v) => setProvider(v as AudioDigestProvider)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {voiceProviders.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Voice Selection */}
          <div className="space-y-2">
            <Label>Voice</Label>
            <Select
              value={voice}
              onValueChange={(v) => setVoice(v as AudioDigestVoice)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {voices.map((v) => (
                  <SelectItem key={v.value} value={v.value}>
                    {v.label} ({v.description})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedVoice && (
              <p className="text-xs text-muted-foreground">
                {selectedVoice.description} voice style
              </p>
            )}
          </div>

          {/* Speed Control */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="flex items-center gap-1.5">
                <Gauge className="h-3.5 w-3.5" />
                Playback Speed
              </Label>
              <span className="text-sm font-medium">{formatSpeed(speed)}</span>
            </div>
            <Slider
              value={[speed]}
              onValueChange={([value]) => setSpeed(value)}
              min={0.5}
              max={2.0}
              step={0.1}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>0.5x</span>
              <span>1.0x</span>
              <span>2.0x</span>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleGenerate} disabled={isGenerating || !digestId}>
            {isGenerating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Headphones className="mr-2 h-4 w-4" />
                Generate Audio
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
