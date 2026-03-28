/**
 * PushNotificationToggle Component
 *
 * Opt-in toggle for push notifications on native platforms (iOS/Android).
 * Hidden on web — push notifications require a native Capacitor shell.
 *
 * Shows permission state and handles the full opt-in flow:
 * request permission -> register with APNs/FCM -> register token with backend.
 */

import { toast } from "sonner"
import { Smartphone } from "lucide-react"

import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { usePushNotifications } from "@/hooks/use-push-notifications"

/** Human-readable permission labels */
const PERMISSION_LABELS: Record<string, string> = {
  granted: "Enabled",
  denied: "Denied",
  prompt: "Not set",
  loading: "Checking...",
}

/** Badge colors for permission states */
const PERMISSION_COLORS: Record<string, string> = {
  granted:
    "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  denied: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  prompt:
    "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  loading:
    "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}

export function PushNotificationToggle() {
  const { permission, isRegistering, enable, disable, isAvailable } =
    usePushNotifications()

  // Don't render on web platforms
  if (!isAvailable) return null

  const isEnabled = permission === "granted"
  const isDenied = permission === "denied" && !isRegistering
  const isLoading = permission === "loading" || isRegistering

  const handleToggle = async (checked: boolean) => {
    if (checked) {
      const success = await enable()
      if (success) {
        toast.success("Push notifications enabled")
      } else if (permission === "denied") {
        toast.error(
          "Push notifications denied. Enable them in your device settings.",
        )
      } else {
        toast.error("Failed to enable push notifications")
      }
    } else {
      await disable()
      toast.success(
        "Push notifications disabled locally. To fully revoke, use device settings.",
      )
    }
  }

  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Smartphone className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Push Notifications</span>
          <Badge
            variant="outline"
            className={`text-[10px] px-1.5 py-0 ${PERMISSION_COLORS[permission] || ""}`}
          >
            {PERMISSION_LABELS[permission] || permission}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5 ml-6">
          {isDenied
            ? "Permission denied by OS. Open device settings to re-enable."
            : "Receive alerts when digests, summaries, or audio are ready."}
        </p>
      </div>
      <Switch
        checked={isEnabled}
        onCheckedChange={handleToggle}
        disabled={isLoading || isDenied}
        aria-label="Toggle push notifications"
      />
    </div>
  )
}
