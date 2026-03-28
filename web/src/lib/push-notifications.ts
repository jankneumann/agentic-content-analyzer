/**
 * Push Notification Utilities
 *
 * Capacitor Push Notifications plugin wrapper for native platforms.
 * All functions are safe to call on web — they return early or no-op.
 *
 * Uses lazy dynamic imports for Capacitor plugins to avoid
 * bundling native-only code in the web build.
 */

import { isNative, getPlatform } from "./platform"
import { apiClient } from "./api/client"
import type { DeviceRegistration } from "@/types"

/**
 * Request push notification permission from the user.
 *
 * Returns "denied" immediately on web platforms.
 *
 * @returns Permission status: "granted", "denied", or "prompt"
 */
export async function requestPushPermission(): Promise<
  "granted" | "denied" | "prompt"
> {
  if (!isNative()) return "denied"

  try {
    const { PushNotifications } = await import(
      "@capacitor/push-notifications"
    )
    const result = await PushNotifications.requestPermissions()
    return result.receive
  } catch {
    return "denied"
  }
}

/**
 * Check current push notification permission status without prompting.
 *
 * @returns Permission status: "granted", "denied", or "prompt"
 */
export async function checkPushPermission(): Promise<
  "granted" | "denied" | "prompt"
> {
  if (!isNative()) return "denied"

  try {
    const { PushNotifications } = await import(
      "@capacitor/push-notifications"
    )
    const result = await PushNotifications.checkPermissions()
    return result.receive
  } catch {
    return "denied"
  }
}

/**
 * Register for push notifications and obtain a device token.
 *
 * Calls `PushNotifications.register()` which triggers APNs/FCM registration.
 * Resolves with the device token string, or null on failure.
 *
 * @returns Device token string or null
 */
export async function registerForPush(): Promise<string | null> {
  if (!isNative()) return null

  try {
    const { PushNotifications } = await import(
      "@capacitor/push-notifications"
    )

    return new Promise<string | null>((resolve) => {
      // Set a timeout so we don't hang forever
      const timeout = setTimeout(() => resolve(null), 10_000)

      PushNotifications.addListener(
        "registration",
        (token: { value: string }) => {
          clearTimeout(timeout)
          resolve(token.value)
        },
      )

      PushNotifications.addListener("registrationError", () => {
        clearTimeout(timeout)
        resolve(null)
      })

      PushNotifications.register()
    })
  } catch {
    return null
  }
}

/**
 * Register a device token with the backend API.
 *
 * POST /api/v1/notifications/devices with platform, token, and delivery method.
 *
 * @param token - Device token from APNs/FCM
 * @returns The created DeviceRegistration, or null on failure
 */
export async function registerDeviceToken(
  token: string,
): Promise<DeviceRegistration | null> {
  try {
    return await apiClient.post<DeviceRegistration>(
      "/notifications/devices",
      {
        platform: getPlatform(),
        token,
        delivery_method: "push",
      },
    )
  } catch {
    return null
  }
}

/**
 * Set up a listener for push notification taps (action performed).
 *
 * When the user taps a push notification, the callback is invoked
 * with the `url` from the notification payload (if present).
 *
 * No-op on web platforms.
 *
 * @param callback - Called with the notification's url (or undefined)
 */
export function onNotificationTap(
  callback: (url?: string) => void,
): void {
  if (!isNative()) return

  import("@capacitor/push-notifications").then(
    ({ PushNotifications }) => {
      PushNotifications.addListener(
        "pushNotificationActionPerformed",
        (action) => {
          const url = action?.notification?.data?.url as string | undefined
          callback(url)
        },
      )
    },
  )
}

/**
 * Listen for token refresh events.
 *
 * On some platforms, the device token may be refreshed by the OS.
 * When this happens, the callback is invoked with the new token
 * so it can be re-registered with the backend.
 *
 * No-op on web platforms.
 *
 * @param callback - Called with the new token string
 */
export function onTokenRefresh(callback: (token: string) => void): void {
  if (!isNative()) return

  import("@capacitor/push-notifications").then(
    ({ PushNotifications }) => {
      PushNotifications.addListener(
        "registration",
        (token: { value: string }) => {
          callback(token.value)
        },
      )
    },
  )
}

/**
 * Remove all push notification listeners.
 *
 * Should be called during cleanup to prevent memory leaks.
 */
export async function removeAllListeners(): Promise<void> {
  if (!isNative()) return

  try {
    const { PushNotifications } = await import(
      "@capacitor/push-notifications"
    )
    await PushNotifications.removeAllListeners()
  } catch {
    // Cleanup should never throw
  }
}
