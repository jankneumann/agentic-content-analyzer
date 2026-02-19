/**
 * Voice Configurator Component
 *
 * Configures TTS settings for audio digests and podcasts.
 * Features:
 * - Provider selection (openai/elevenlabs)
 * - Default voice configuration
 * - Speed slider (0.5x to 2.0x)
 * - Voice presets as clickable cards
 * - Source badges showing where each value comes from
 * - Reset-to-default for db overrides
 * - Disabled controls when env var takes precedence
 */

import { useState } from "react"
import { RotateCcw, AlertCircle, RefreshCw, Lock, Volume2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Slider } from "@/components/ui/slider"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { useVoiceSettings, useUpdateVoice, useResetVoice } from "@/hooks/use-settings"
import type { VoiceSettingInfo } from "@/types/settings"

/** Badge color classes by source type */
const SOURCE_BADGE_CLASSES: Record<string, string> = {
  env: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800",
  db: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800",
  default: "bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800/50 dark:text-gray-400 dark:border-gray-700",
}

function SourceBadge({ source }: { source: string }) {
  return (
    <Badge
      variant="outline"
      className={`text-[10px] px-1.5 py-0 shrink-0 ${SOURCE_BADGE_CLASSES[source] ?? SOURCE_BADGE_CLASSES.default}`}
    >
      {source}
    </Badge>
  )
}

/** Wraps a control with a lock tooltip when the value is set by env var */
function EnvLockWrapper({
  source,
  children,
}: {
  source: string
  children: React.ReactNode
}) {
  if (source !== "env") {
    return <>{children}</>
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="relative">
            {children}
            <div className="absolute inset-0 cursor-not-allowed" />
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <div className="flex items-center gap-1.5 text-xs">
            <Lock className="h-3 w-3" />
            Set by environment variable
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export function VoiceConfigurator() {
  const { data, isLoading, isError, error, refetch } = useVoiceSettings()
  const updateMutation = useUpdateVoice()
  const resetMutation = useResetVoice()

  // Local speed state for smooth slider interaction
  const [localSpeed, setLocalSpeed] = useState<number | null>(null)
  // Local voice state for debounced text input
  const [localVoice, setLocalVoice] = useState<string | null>(null)

  const handleUpdate = (field: string, value: string) => {
    updateMutation.mutate({ field, value })
  }

  const handleReset = (field: string) => {
    resetMutation.mutate(field)
    if (field === "speed") {
      setLocalSpeed(null)
    }
  }

  const handleSpeedCommit = (values: number[]) => {
    const newSpeed = values[0]
    setLocalSpeed(null)
    handleUpdate("speed", String(newSpeed))
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-5" />
          <Skeleton className="h-5 w-32" />
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-full" />
          </div>
        ))}
      </div>
    )
  }

  // Error state
  if (isError) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed">
        <div className="text-center">
          <AlertCircle className="mx-auto h-10 w-10 text-destructive/50" />
          <p className="mt-2 text-sm text-muted-foreground">
            Failed to load voice settings: {error?.message}
          </p>
          <Button className="mt-3" size="sm" variant="outline" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  if (!data) return null

  const currentSpeed = localSpeed ?? parseFloat(data.speed.value)

  return (
    <div className="space-y-6">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <Volume2 className="h-5 w-5 text-muted-foreground" />
        <h3 className="text-sm font-medium">Voice Settings</h3>
      </div>

      {/* Provider */}
      <SettingRow label="Provider" setting={data.provider} onReset={() => handleReset("provider")}>
        <EnvLockWrapper source={data.provider.source}>
          <Select
            value={data.provider.value}
            onValueChange={(v) => handleUpdate("provider", v)}
            disabled={data.provider.source === "env"}
          >
            <SelectTrigger size="sm" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {data.valid_providers.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </EnvLockWrapper>
      </SettingRow>

      {/* Default Voice */}
      <SettingRow
        label="Default Voice"
        setting={data.default_voice}
        onReset={() => handleReset("default_voice")}
      >
        <EnvLockWrapper source={data.default_voice.source}>
          <input
            type="text"
            value={localVoice ?? data.default_voice.value}
            onChange={(e) => setLocalVoice(e.target.value)}
            onBlur={() => {
              if (localVoice !== null && localVoice !== data.default_voice.value) {
                handleUpdate("default_voice", localVoice)
              }
              setLocalVoice(null)
            }}
            disabled={data.default_voice.source === "env"}
            className="flex h-8 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            placeholder="e.g. alloy, shimmer, onyx"
          />
        </EnvLockWrapper>
      </SettingRow>

      {/* Speed */}
      <SettingRow label="Speed" setting={data.speed} onReset={() => handleReset("speed")}>
        <EnvLockWrapper source={data.speed.source}>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-2xl font-semibold tabular-nums">
                {currentSpeed.toFixed(1)}x
              </span>
            </div>
            <Slider
              value={[currentSpeed]}
              onValueChange={(values) => setLocalSpeed(values[0])}
              onValueCommit={handleSpeedCommit}
              min={0.5}
              max={2.0}
              step={0.1}
              disabled={data.speed.source === "env"}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>0.5x</span>
              <span>1.0x</span>
              <span>1.5x</span>
              <span>2.0x</span>
            </div>
          </div>
        </EnvLockWrapper>
      </SettingRow>

      {/* Presets */}
      {data.presets.length > 0 && (
        <div className="space-y-2">
          <Label className="text-sm font-medium text-muted-foreground">
            Voice Presets
          </Label>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {data.presets.map((preset) => (
              <button
                key={preset.name}
                type="button"
                onClick={() => {
                  // Apply the voice for the current provider
                  const voice = preset.voices[data.provider.value]
                  if (voice && data.default_voice.source !== "env") {
                    handleUpdate("default_voice", voice)
                  }
                }}
                disabled={data.default_voice.source === "env"}
                className="flex flex-col items-start gap-1.5 rounded-md border bg-card p-3 text-left transition-colors hover:bg-accent/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className="text-sm font-medium">{preset.name}</span>
                <div className="flex flex-wrap gap-1">
                  {Object.entries(preset.voices).map(([provider, voice]) => (
                    <Badge
                      key={provider}
                      variant={provider === data.provider.value ? "default" : "outline"}
                      className="text-[10px] px-1.5 py-0"
                    >
                      {provider}: {voice}
                    </Badge>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/** Reusable row layout for a single setting with label, source badge, and reset button */
function SettingRow({
  label,
  setting,
  onReset,
  children,
}: {
  label: string
  setting: VoiceSettingInfo
  onReset: () => void
  children: React.ReactNode
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Label className="text-sm font-medium">{label}</Label>
        <SourceBadge source={setting.source} />
        {setting.source === "db" && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            className="h-6 px-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="h-3 w-3 mr-1" />
            Reset
          </Button>
        )}
      </div>
      {children}
    </div>
  )
}
