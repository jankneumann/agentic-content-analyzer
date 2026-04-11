/**
 * Model Configurator Component
 *
 * Lets users select which LLM model to use for each pipeline step.
 * Each step shows a dropdown grouped by model family, with cost info
 * and a source badge indicating where the current value comes from.
 *
 * Features:
 * - Per-step model selection via grouped dropdown
 * - Source badges: env (amber), db (blue), default (gray)
 * - Cost per MTok displayed in dropdown options
 * - Reset button for db-overridden steps
 * - Disabled select with tooltip when env var takes precedence
 * - Loading skeletons and error state with retry
 */

import { useMemo } from "react"
import { RotateCcw, AlertCircle, RefreshCw, Lock } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useModelSettings, useUpdateModel, useResetModel } from "@/hooks/use-settings"
import type { StepConfig, ModelOption } from "@/types/settings"

/** Format cost per million tokens for display */
function formatCost(cost: number | null): string {
  if (cost === null) return "\u2014"
  if (cost < 1) return `$${cost.toFixed(2)}/MTok`
  return `$${cost.toFixed(1)}/MTok`
}

/** Format a pipeline step name for display (e.g., "theme_analysis" -> "Theme Analysis") */
function formatStepName(step: string): string {
  return step
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}

/** Group models by their family for organized dropdown sections */
function groupByFamily(models: ModelOption[]): Record<string, ModelOption[]> {
  const groups: Record<string, ModelOption[]> = {}
  for (const model of models) {
    const family = model.family
    if (!groups[family]) {
      groups[family] = []
    }
    groups[family].push(model)
  }
  // Sort models within each family by name
  for (const key of Object.keys(groups)) {
    groups[key].sort((a, b) => a.name.localeCompare(b.name))
  }
  return groups
}

/** Capability requirements per pipeline step — filters model dropdown to eligible models */
const STEP_CAPABILITY_FILTERS: Partial<Record<string, (model: ModelOption) => boolean>> = {
  cloud_stt: (m) => m.supports_audio,
}

/** Badge color classes by source type */
const SOURCE_BADGE_CLASSES: Record<StepConfig["source"], string> = {
  env: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  db: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400",
  default: "border-border bg-muted text-muted-foreground",
}

/** Render a single pipeline step row */
function StepRow({
  step,
  modelsByFamily,
  families,
}: {
  step: StepConfig
  modelsByFamily: Record<string, ModelOption[]>
  families: string[]
}) {
  const updateModel = useUpdateModel()
  const resetModel = useResetModel()

  const isEnvLocked = step.source === "env"
  const isDbOverridden = step.source === "db"

  return (
    <div className="flex items-center gap-3 rounded-md border bg-card px-3 py-3">
      {/* Step name and env var */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {formatStepName(step.step)}
          </span>
          <Badge
            className={`text-[10px] px-1.5 py-0 ${SOURCE_BADGE_CLASSES[step.source]}`}
          >
            {step.source}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground font-mono truncate mt-0.5">
          {step.env_var}
        </p>
      </div>

      {/* Model selector */}
      <div className="flex items-center gap-2 shrink-0">
        {isEnvLocked ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-2">
                  <Select disabled value={step.current_model}>
                    <SelectTrigger className="w-[220px]" size="sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent />
                  </Select>
                  <Lock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p>Set via environment variable. Remove {step.env_var} to configure here.</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : (
          <Select
            value={step.current_model}
            onValueChange={(modelId) =>
              updateModel.mutate({ step: step.step, modelId })
            }
          >
            <SelectTrigger className="w-[220px]" size="sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {families.map((family) => (
                <SelectGroup key={family}>
                  <SelectLabel>{family}</SelectLabel>
                  {modelsByFamily[family].map((model) => (
                    <SelectItem key={model.id} value={model.id}>
                      <span className="flex items-center gap-2">
                        <span>{model.name}</span>
                        <span className="text-[10px] text-muted-foreground">
                          {formatCost(model.cost_per_mtok_input)} in / {formatCost(model.cost_per_mtok_output)} out
                        </span>
                      </span>
                    </SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Reset button (only shown for db overrides) */}
        {isDbOverridden && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 shrink-0"
                  onClick={() => resetModel.mutate(step.step)}
                  disabled={resetModel.isPending}
                  aria-label="Reset to default"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Reset to default ({step.default_model})</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
    </div>
  )
}

export function ModelConfigurator() {
  const { data, isLoading, isError, error, refetch } = useModelSettings()

  // Group available models by family
  const modelsByFamily = useMemo(
    () => (data?.available_models ? groupByFamily(data.available_models) : {}),
    [data]
  )
  const families = useMemo(
    () => Object.keys(modelsByFamily).sort(),
    [modelsByFamily]
  )

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
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
            Failed to load model settings: {error?.message}
          </p>
          <Button className="mt-3" size="sm" variant="outline" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  // Empty state
  if (!data?.steps?.length) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed">
        <p className="text-sm text-muted-foreground">
          No pipeline steps configured
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {data.steps.map((step) => {
        const filter = STEP_CAPABILITY_FILTERS[step.step]
        const stepModelsByFamily = filter
          ? groupByFamily(data.available_models.filter(filter))
          : modelsByFamily
        const stepFamilies = filter
          ? Object.keys(stepModelsByFamily).sort()
          : families
        return (
          <StepRow
            key={step.step}
            step={step}
            modelsByFamily={stepModelsByFamily}
            families={stepFamilies}
          />
        )
      })}
    </div>
  )
}
