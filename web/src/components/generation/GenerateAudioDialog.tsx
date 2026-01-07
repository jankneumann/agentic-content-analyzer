/**
 * GenerateAudioDialog Component
 *
 * Dialog for configuring and triggering podcast audio generation.
 * Allows selecting:
 * - Source script
 * - Voice provider
 * - Voice personas for Alex and Sam
 */

import * as React from "react"
import { Loader2, Volume2, User } from "lucide-react"

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
import type { ScriptListItem } from "@/types"

interface GenerateAudioDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onGenerate: (params: AudioGenerationParams) => void
  isGenerating?: boolean
  scripts?: ScriptListItem[]
  preselectedScriptId?: number
}

export interface AudioGenerationParams {
  script_id: number
  voice_provider: string
  alex_voice: string
  sam_voice: string
}

const voiceProviders = [
  { value: "openai_tts", label: "OpenAI TTS" },
  { value: "elevenlabs", label: "ElevenLabs" },
]

const alexVoices = [
  { value: "alex_male", label: "Alex (Male, Default)" },
  { value: "onyx", label: "Onyx (Deep Male)" },
  { value: "echo", label: "Echo (Natural Male)" },
]

const samVoices = [
  { value: "sam_female", label: "Sam (Female, Default)" },
  { value: "nova", label: "Nova (Warm Female)" },
  { value: "shimmer", label: "Shimmer (Expressive Female)" },
]

export function GenerateAudioDialog({
  open,
  onOpenChange,
  onGenerate,
  isGenerating = false,
  scripts = [],
  preselectedScriptId,
}: GenerateAudioDialogProps) {
  // Form state
  const [scriptId, setScriptId] = React.useState<number | null>(preselectedScriptId ?? null)
  const [voiceProvider, setVoiceProvider] = React.useState("openai_tts")
  const [alexVoice, setAlexVoice] = React.useState("alex_male")
  const [samVoice, setSamVoice] = React.useState("sam_female")

  // Update script ID when preselected changes
  React.useEffect(() => {
    if (preselectedScriptId) {
      setScriptId(preselectedScriptId)
    }
  }, [preselectedScriptId])

  // Filter to approved scripts
  const approvedScripts = scripts.filter((s) => s.status === "script_approved")

  const handleGenerate = () => {
    if (!scriptId) return

    onGenerate({
      script_id: scriptId,
      voice_provider: voiceProvider,
      alex_voice: alexVoice,
      sam_voice: samVoice,
    })
  }

  const selectedScript = scripts.find((s) => s.id === scriptId)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Volume2 className="h-5 w-5" />
            Generate Podcast Audio
          </DialogTitle>
          <DialogDescription>
            Synthesize audio from an approved podcast script.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Source Script */}
          <div className="space-y-2">
            <Label>Source Script</Label>
            <Select
              value={scriptId ? String(scriptId) : ""}
              onValueChange={(v) => setScriptId(Number(v))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select an approved script..." />
              </SelectTrigger>
              <SelectContent>
                {approvedScripts.length === 0 ? (
                  <SelectItem value="" disabled>
                    No approved scripts available
                  </SelectItem>
                ) : (
                  approvedScripts.map((script) => (
                    <SelectItem key={script.id} value={String(script.id)}>
                      [{script.id}] {script.title ?? `Script #${script.id}`}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
            {selectedScript && (
              <p className="text-xs text-muted-foreground">
                {selectedScript.length} • {selectedScript.estimated_duration} • {selectedScript.word_count} words
              </p>
            )}
          </div>

          {/* Voice Provider */}
          <div className="space-y-2">
            <Label>Voice Provider</Label>
            <Select value={voiceProvider} onValueChange={setVoiceProvider}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {voiceProviders.map((provider) => (
                  <SelectItem key={provider.value} value={provider.value}>
                    {provider.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Voice Selection */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5">
                <User className="h-3.5 w-3.5 text-blue-600" />
                Alex Voice
              </Label>
              <Select value={alexVoice} onValueChange={setAlexVoice}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {alexVoices.map((voice) => (
                    <SelectItem key={voice.value} value={voice.value}>
                      {voice.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">VP of Engineering</p>
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5">
                <User className="h-3.5 w-3.5 text-purple-600" />
                Sam Voice
              </Label>
              <Select value={samVoice} onValueChange={setSamVoice}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {samVoices.map((voice) => (
                    <SelectItem key={voice.value} value={voice.value}>
                      {voice.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">Distinguished Engineer</p>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleGenerate} disabled={isGenerating || !scriptId}>
            {isGenerating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Volume2 className="mr-2 h-4 w-4" />
                Generate Audio
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
