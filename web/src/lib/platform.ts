/**
 * Platform Detection Utilities
 *
 * Detects whether the app is running as a native Capacitor app or in a web browser.
 * Used by haptics, status bar, share target, push notifications, and STT engine.
 */

import { Capacitor } from "@capacitor/core"

export type Platform = "ios" | "android" | "web"

/**
 * Check if the app is running as a native Capacitor app (iOS or Android).
 */
export function isNative(): boolean {
  return Capacitor.isNativePlatform()
}

/**
 * Get the current platform: "ios", "android", or "web".
 */
export function getPlatform(): Platform {
  return Capacitor.getPlatform() as Platform
}
