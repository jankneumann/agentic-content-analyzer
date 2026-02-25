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
import { RotateCcw, AlertCircle, RefreshCw, Lock, Volume2, Mic, Cloud, ChevronUp, ChevronDown } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Slider } from "@/components/ui/slider"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useVoiceSettings, useUpdateVoice, useResetVoice } from "@/hooks/use-settings"
import type { VoiceSettingInfo } from "@/types/settings"

/** Human-readable language labels */
const LANGUAGE_LABELS: Record<string, string> = {
  "en-US": "English (US)",
  "en-GB": "English (UK)",
  "es-ES": "Spanish",
  "fr-FR": "French",
  "de-DE": "German",
  "ja-JP": "Japanese",
  "zh-CN": "Chinese (Simplified)",
}

/** Human-readable engine labels */
const ENGINE_LABELS: Record<string, string> = {
  cloud: "Cloud STT",
  native: "Native (OS-level)",
  browser: "Browser (Web Speech API)",
  "on-device": "On-device (local model)",
}

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
      <SettingRow
        label="Provider"
        setting={data.provider}
        onReset={() => handleReset("provider")}
        controlId="voice-provider"
      >
        <EnvLockWrapper source={data.provider.source}>
          <Select
            value={data.provider.value}
            onValueChange={(v) => handleUpdate("provider", v)}
            disabled={data.provider.source === "env"}
          >
            <SelectTrigger
              size="sm"
              className="w-full"
              aria-labelledby="voice-provider-label"
            >
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
        controlId="default-voice"
      >
        <EnvLockWrapper source={data.default_voice.source}>
          <input
            id="default-voice"
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
      <SettingRow
        label="Speed"
        setting={data.speed}
        onReset={() => handleReset("speed")}
        controlId="voice-speed"
      >
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
              aria-labelledby="voice-speed-label"
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

      {/* Separator */}
      <div className="border-t" />

      {/* Voice Input section */}
      <div className="flex items-center gap-2">
        <Mic className="h-5 w-5 text-muted-foreground" />
        <h3 className="text-sm font-medium">Voice Input</h3>
      </div>

      {/* Input Language */}
      <SettingRow
        label="Language"
        setting={data.input_language}
        onReset={() => handleReset("input_language")}
        controlId="input-language"
      >
        <EnvLockWrapper source={data.input_language.source}>
          <Select
            value={data.input_language.value}
            onValueChange={(v) => handleUpdate("input_language", v)}
            disabled={data.input_language.source === "env"}
          >
            <SelectTrigger
              size="sm"
              className="w-full"
              aria-labelledby="input-language-label"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {data.valid_input_languages.map((lang) => (
                <SelectItem key={lang} value={lang}>
                  {LANGUAGE_LABELS[lang] ?? lang}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </EnvLockWrapper>
      </SettingRow>

      {/* Continuous Mode */}
      <SettingRow
        label="Continuous Mode"
        setting={data.input_continuous}
        onReset={() => handleReset("input_continuous")}
        controlId="continuous-mode"
      >
        <EnvLockWrapper source={data.input_continuous.source}>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground" id="continuous-mode-desc">
              Keep listening after pauses instead of stopping after each utterance
            </p>
            <Switch
              id="continuous-mode"
              checked={data.input_continuous.value === "true"}
              onCheckedChange={(checked) =>
                handleUpdate("input_continuous", String(checked))
              }
              disabled={data.input_continuous.source === "env"}
              aria-describedby="continuous-mode-desc"
            />
          </div>
        </EnvLockWrapper>
      </SettingRow>

      {/* Auto-Submit */}
      <SettingRow
        label="Auto-Submit"
        setting={data.input_auto_submit}
        onReset={() => handleReset("input_auto_submit")}
        controlId="auto-submit"
      >
        <EnvLockWrapper source={data.input_auto_submit.source}>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground" id="auto-submit-desc">
              Automatically send message when voice input ends (single-utterance mode only)
            </p>
            <Switch
              id="auto-submit"
              checked={data.input_auto_submit.value === "true"}
              onCheckedChange={(checked) =>
                handleUpdate("input_auto_submit", String(checked))
              }
              disabled={data.input_auto_submit.source === "env"}
              aria-describedby="auto-submit-desc"
            />
          </div>
        </EnvLockWrapper>
      </SettingRow>

      {/* Separator */}
      <div className="border-t" />

      {/* Cloud STT section */}
      <div className="flex items-center gap-2">
        <Cloud className="h-5 w-5 text-muted-foreground" />
        <h3 className="text-sm font-medium">Cloud Speech-to-Text</h3>
      </div>

      {/* Cloud STT Model (read-only badge linking to Model Config section) */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Model</Label>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="cursor-pointer hover:bg-accent transition-colors"
            onClick={() => {
              document.getElementById("model-configuration")?.scrollIntoView({ behavior: "smooth" })
            }}
          >
            {data.cloud_stt_model}
          </Badge>
          <span className="text-xs text-muted-foreground">
            Change in Model Configuration above
          </span>
        </div>
      </div>

      {/* Cloud STT Language */}
      <SettingRow
        label="Cloud STT Language"
        setting={data.cloud_stt_language}
        onReset={() => handleReset("cloud_stt_language")}
        controlId="cloud-stt-language"
      >
        <EnvLockWrapper source={data.cloud_stt_language.source}>
          <Select
            value={data.cloud_stt_language.value}
            onValueChange={(v) => handleUpdate("cloud_stt_language", v)}
            disabled={data.cloud_stt_language.source === "env"}
          >
            <SelectTrigger
              size="sm"
              className="w-full"
              aria-labelledby="cloud-stt-language-label"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {data.valid_cloud_stt_languages.map((lang) => (
                <SelectItem key={lang} value={lang}>
                  {lang === "auto" ? "Auto-detect" : (LANGUAGE_LABELS[lang] ?? lang)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </EnvLockWrapper>
      </SettingRow>

      {/* Engine Preference Order */}
      <SettingRow
        label="Engine Preference"
        setting={data.engine_preference_order}
        onReset={() => handleReset("engine_preference_order")}
      >
        <EnvLockWrapper source={data.engine_preference_order.source}>
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Priority order for speech-to-text engines. Higher entries are preferred.
            </p>
            <EnginePreferenceList
              value={data.engine_preference_order.value}
              disabled={data.engine_preference_order.source === "env"}
              onChange={(newOrder) => handleUpdate("engine_preference_order", newOrder)}
            />
          </div>
        </EnvLockWrapper>
      </SettingRow>
    </div>
  )
}

/** Engine preference order list with up/down reordering */
function EnginePreferenceList({
  value,
  disabled,
  onChange,
}: {
  value: string
  disabled: boolean
  onChange: (newValue: string) => void
}) {
  const engines = value.split(",").map((e) => e.trim())

  const moveUp = (index: number) => {
    if (index === 0) return
    const newOrder = [...engines]
    ;[newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]]
    onChange(newOrder.join(","))
  }

  const moveDown = (index: number) => {
    if (index === engines.length - 1) return
    const newOrder = [...engines]
    ;[newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]]
    onChange(newOrder.join(","))
  }

  return (
    <div className="space-y-1">
      {engines.map((engine, index) => (
        <div
          key={engine}
          className="flex items-center gap-2 rounded-md border bg-card px-3 py-2"
        >
          <span className="text-xs text-muted-foreground w-4">{index + 1}.</span>
          <span className="text-sm flex-1">{ENGINE_LABELS[engine] ?? engine}</span>
          <div className="flex gap-0.5">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              disabled={disabled || index === 0}
              onClick={() => moveUp(index)}
            >
              <ChevronUp className="h-3.5 w-3.5" />
              <span className="sr-only">Move up</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              disabled={disabled || index === engines.length - 1}
              onClick={() => moveDown(index)}
            >
              <ChevronDown className="h-3.5 w-3.5" />
              <span className="sr-only">Move down</span>
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}

/** Reusable row layout for a single setting with label, source badge, and reset button */
function SettingRow({
  label,
  setting,
  onReset,
  children,
  controlId,
}: {
  label: string
  setting: VoiceSettingInfo
  onReset: () => void
  children: React.ReactNode
  controlId?: string
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Label
          className="text-sm font-medium"
          htmlFor={controlId}
          id={controlId ? `${controlId}-label` : undefined}
        >
          {label}
        </Label>
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
