/**
 * Platform Detection Utilities
 *
 * Detects whether the app is running as:
 * - A Tauri v2 desktop app (macOS, Windows, Linux)
 * - A native Capacitor app (iOS or Android)
 * - A web browser
 *
 * Used by haptics, status bar, share target, push notifications,
 * STT engine, system tray, global shortcuts, and file drop.
 */

import { Capacitor } from "@capacitor/core"

export type Platform = "desktop" | "ios" | "android" | "web"

/**
 * Check if the app is running inside a Tauri v2 desktop shell.
 * Tauri injects __TAURI_INTERNALS__ into the webview global scope.
 */
export function isTauri(): boolean {
  return (
    typeof window !== "undefined" &&
    "__TAURI_INTERNALS__" in window
  )
}

/**
 * Check if the app is running as a native Capacitor app (iOS or Android).
 */
export function isNative(): boolean {
  return Capacitor.isNativePlatform()
}

/**
 * Get the current platform: "desktop", "ios", "android", or "web".
 *
 * Detection order matters: Tauri is checked first because Capacitor's
 * getPlatform() returns "web" inside Tauri's webview (no native bridge).
 */
export function getPlatform(): Platform {
  if (isTauri()) return "desktop"
  return Capacitor.getPlatform() as Platform
}
