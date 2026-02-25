/**
 * NotificationConfigurator Component
 *
 * Per-event-type notification preference toggles with source badges.
 * Follows the same pattern as VoiceConfigurator.
 */

import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useNotificationPreferences,
  useUpdateNotificationPreference,
} from "@/hooks/use-notifications"
import type { NotificationPreference } from "@/types"

/** Human-readable labels for event types */
const EVENT_TYPE_LABELS: Record<string, string> = {
  batch_summary: "Batch Summary",
  theme_analysis: "Theme Analysis",
  digest_creation: "Digest Creation",
  script_generation: "Script Generation",
  audio_generation: "Audio Generation",
  pipeline_completion: "Pipeline Completion",
  job_failure: "Job Failure",
}

/** Source badge colors */
const SOURCE_COLORS: Record<string, string> = {
  env: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  db: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  default: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}

function PreferenceRow({ preference }: { preference: NotificationPreference }) {
  const updatePref = useUpdateNotificationPreference()
  // const resetPref = useResetNotificationPreference()

  const isEnvControlled = preference.source === "env"

  const handleToggle = (checked: boolean) => {
    updatePref.mutate(
      { eventType: preference.event_type, enabled: checked },
      {
        onSuccess: () => {
          toast.success(
            `${EVENT_TYPE_LABELS[preference.event_type] || preference.event_type} notifications ${checked ? "enabled" : "disabled"}`
          )
        },
        onError: () => {
          toast.error("Failed to update preference")
        },
      }
    )
  }

  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {EVENT_TYPE_LABELS[preference.event_type] || preference.event_type}
          </span>
          <Badge
            variant="outline"
            className={`text-[10px] px-1.5 py-0 ${SOURCE_COLORS[preference.source] || ""}`}
          >
            {preference.source}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          {preference.description}
        </p>
      </div>
      <Switch
        checked={preference.enabled}
        onCheckedChange={handleToggle}
        disabled={isEnvControlled || updatePref.isPending}
        aria-label={`Toggle ${EVENT_TYPE_LABELS[preference.event_type]} notifications`}
      />
    </div>
  )
}

export function NotificationConfigurator() {
  const { data, isLoading, error } = useNotificationPreferences()

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between py-3">
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
            </div>
            <Skeleton className="h-5 w-9" />
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <p className="text-sm text-destructive">
        Failed to load notification preferences.
      </p>
    )
  }

  const preferences = data?.preferences ?? []

  return (
    <div className="divide-y">
      {preferences.map((pref) => (
        <PreferenceRow key={pref.event_type} preference={pref} />
      ))}
    </div>
  )
}
