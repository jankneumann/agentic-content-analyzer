/**
 * Push Notification Hooks
 *
 * React hooks for managing push notification lifecycle:
 * - Permission request and status tracking
 * - Device token registration with backend
 * - Token refresh handling
 * - SSE-to-local-notification bridging (foreground delivery)
 * - Notification tap handling (deep linking)
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate } from "@tanstack/react-router"

import { isNative } from "@/lib/platform"
import {
  requestPushPermission,
  checkPushPermission,
  registerForPush,
  registerDeviceToken,
  onNotificationTap,
  onTokenRefresh,
  removeAllListeners,
} from "@/lib/push-notifications"
import type { NotificationEvent } from "@/types"

export type PushPermissionStatus = "granted" | "denied" | "prompt" | "loading"

/**
 * Hook for managing push notification opt-in and device registration.
 *
 * Handles the full lifecycle:
 * 1. Check current permission status on mount
 * 2. Request permission when user opts in
 * 3. Register device token with backend
 * 4. Handle token refresh
 * 5. Clean up listeners on unmount
 *
 * Returns permission status and an enable/disable function for the settings toggle.
 */
export function usePushNotifications() {
  const [permission, setPermission] = useState<PushPermissionStatus>("loading")
  const [isRegistering, setIsRegistering] = useState(false)
  const tokenRef = useRef<string | null>(null)

  // Check permission status on mount
  useEffect(() => {
    if (!isNative()) {
      setPermission("denied")
      return
    }

    checkPushPermission().then(setPermission)
  }, [])

  // Handle token refresh — re-register with backend
  useEffect(() => {
    if (!isNative() || permission !== "granted") return

    onTokenRefresh(async (newToken) => {
      tokenRef.current = newToken
      await registerDeviceToken(newToken)
    })

    return () => {
      removeAllListeners()
    }
  }, [permission])

  /**
   * Enable push notifications: request permission, register token.
   *
   * @returns true if push was successfully enabled
   */
  const enable = useCallback(async (): Promise<boolean> => {
    if (!isNative()) return false

    setIsRegistering(true)
    try {
      const status = await requestPushPermission()
      setPermission(status)

      if (status !== "granted") return false

      const token = await registerForPush()
      if (!token) return false

      tokenRef.current = token
      const registration = await registerDeviceToken(token)
      return registration !== null
    } finally {
      setIsRegistering(false)
    }
  }, [])

  /**
   * Disable push notifications.
   *
   * Note: On iOS/Android, you cannot programmatically revoke push permission.
   * This removes listeners and clears the local token reference.
   * The user must disable notifications in OS settings.
   */
  const disable = useCallback(async () => {
    tokenRef.current = null
    await removeAllListeners()
  }, [])

  return {
    /** Current permission status */
    permission,
    /** Whether a registration attempt is in progress */
    isRegistering,
    /** Enable push notifications */
    enable,
    /** Disable push notifications (local only) */
    disable,
    /** Whether push is available on this platform */
    isAvailable: isNative(),
  }
}

/**
 * Hook for triggering local notifications from SSE events when the app is
 * in the foreground.
 *
 * Pass this as the `onEvent` callback to `useNotificationSSE()`.
 * On native platforms, it shows a local notification via the Capacitor
 * LocalNotifications plugin. On web, it's a no-op (web already has
 * the NotificationBell UI).
 */
export function useLocalNotificationBridge() {
  const idCounter = useRef(0)

  const showLocalNotification = useCallback(
    async (event: NotificationEvent) => {
      if (!isNative()) return

      try {
        const { LocalNotifications } = await import(
          "@capacitor/local-notifications"
        )

        idCounter.current += 1

        await LocalNotifications.schedule({
          notifications: [
            {
              id: idCounter.current,
              title: event.title,
              body: event.summary || "",
              extra: {
                url: (event.payload?.url as string) || "",
                event_id: event.id,
              },
            },
          ],
        })
      } catch {
        // Local notification delivery should never break the app
      }
    },
    [],
  )

  return showLocalNotification
}

/**
 * Hook for handling notification taps — navigates to the payload URL.
 *
 * Sets up a listener on mount that fires when the user taps a
 * push or local notification. Navigates to the URL in the payload.
 *
 * Must be mounted once at the app root level.
 */
export function useNotificationTapHandler() {
  const navigate = useNavigate()

  useEffect(() => {
    if (!isNative()) return

    // Handle push notification taps
    onNotificationTap((url) => {
      if (url) {
        navigate({ to: url })
      }
    })

    // Handle local notification taps
    import("@capacitor/local-notifications").then(
      ({ LocalNotifications }) => {
        LocalNotifications.addListener(
          "localNotificationActionPerformed",
          (action) => {
            const url = action?.notification?.extra?.url as
              | string
              | undefined
            if (url) {
              navigate({ to: url })
            }
          },
        )
      },
    )

    return () => {
      removeAllListeners()
      import("@capacitor/local-notifications").then(
        ({ LocalNotifications }) => {
          LocalNotifications.removeAllListeners()
        },
      )
    }
  }, [navigate])
}
