/**
 * Share Target Handler
 *
 * Initializes listeners for:
 * 1. App state changes — checks for pending shares from iOS Share Extension
 *    (Share Extension writes URL to App Group; main app reads on activation)
 * 2. Network status changes — flushes offline queue on reconnect
 *
 * On iOS, the Share Extension writes the shared URL to the App Group shared
 * container (UserDefaults suite). The main app reads and clears it when
 * activated. This is a Capacitor convention using @capacitor/preferences
 * with a shared App Group.
 *
 * Tasks 6.1-6.3 (iOS Share Extension Swift code) are Xcode-only.
 * Task 6.4 (Android intent filter) is scaffolded/deferred.
 */

import { App } from "@capacitor/app"
import { Network } from "@capacitor/network"
import { isNative } from "../platform"
import { triggerNotification } from "../haptics"
import { validateShareUrl, extractUrl } from "./url-validator"
import { enqueue, flushQueue } from "./offline-queue"
import { saveUrl } from "../api/contents"
import { toast } from "sonner"

/**
 * Attempt to save a URL via the API.
 * Returns true on success, false on failure.
 */
async function trySaveUrl(url: string): Promise<boolean> {
  try {
    await saveUrl({ url })
    return true
  } catch {
    return false
  }
}

/**
 * Process a shared URL: validate, save via API, or queue offline.
 */
async function processSharedUrl(rawUrl: string): Promise<void> {
  // Try to extract a URL if the shared text contains surrounding content
  const url = extractUrl(rawUrl) ?? rawUrl.trim()

  const validation = validateShareUrl(url)
  if (!validation.valid) {
    toast.error(validation.error ?? "Invalid URL")
    await triggerNotification("error")
    return
  }

  const success = await trySaveUrl(url)

  if (success) {
    toast.success("URL saved for processing")
    await triggerNotification("success")
  } else {
    // Queue for offline retry
    await enqueue(url)
    toast.info("Offline — URL queued for later")
    await triggerNotification("warning")
  }
}

/**
 * Check for pending shares from the iOS Share Extension.
 *
 * The Share Extension writes to the App Group shared UserDefaults.
 * Capacitor Preferences can read from the same App Group when configured.
 * The key convention is `PENDING_SHARE_URL`.
 */
async function checkForPendingShares(): Promise<void> {
  try {
    // Dynamic import to avoid bundling in web builds
    const { Preferences } = await import("@capacitor/preferences")
    const { value } = await Preferences.get({ key: "PENDING_SHARE_URL" })

    if (value) {
      // Clear immediately to prevent re-processing
      await Preferences.remove({ key: "PENDING_SHARE_URL" })
      await processSharedUrl(value)
    }
  } catch {
    // Share Extension check is best-effort
  }
}

/**
 * Initialize the share target handler.
 *
 * Safe to call on any platform — exits early on web.
 * Should be called once during app initialization.
 */
export function initShareTarget(): void {
  if (!isNative()) return

  // Listen for app activation to check for pending shares from Share Extension
  App.addListener("appStateChange", async ({ isActive }) => {
    if (isActive) {
      await checkForPendingShares()
    }
  })

  // Listen for network changes to flush offline queue
  Network.addListener("networkStatusChange", async ({ connected }) => {
    if (connected) {
      const flushed = await flushQueue(trySaveUrl)
      if (flushed > 0) {
        toast.success(
          `Saved ${flushed} queued ${flushed === 1 ? "URL" : "URLs"}`,
        )
        await triggerNotification("success")
      }
    }
  })

  // Also check for pending shares on initial load
  checkForPendingShares()
}
