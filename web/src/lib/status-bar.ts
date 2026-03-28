/**
 * Status Bar Integration
 *
 * Manages the native status bar appearance on iOS/Android via @capacitor/status-bar.
 * All functions are no-ops on web — safe to call unconditionally.
 *
 * Uses lazy dynamic imports to avoid bundling native-only code in the web build.
 */

import { isNative } from "./platform"

/**
 * Set the status bar style to match the current theme.
 *
 * @param isDark - Whether the app is in dark mode
 */
export async function updateStatusBarStyle(isDark: boolean): Promise<void> {
  if (!isNative()) return

  try {
    const { StatusBar, Style } = await import("@capacitor/status-bar")
    await StatusBar.setStyle({
      style: isDark ? Style.Dark : Style.Light,
    })
  } catch {
    // Status bar should never break the app
  }
}

/**
 * Set the status bar background color.
 *
 * @param color - CSS hex color string (e.g., "#ffffff")
 */
export async function setStatusBarColor(color: string): Promise<void> {
  if (!isNative()) return

  try {
    const { StatusBar } = await import("@capacitor/status-bar")
    await StatusBar.setBackgroundColor({ color })
  } catch {
    // Status bar should never break the app
  }
}

/**
 * Show the status bar (if previously hidden).
 */
export async function showStatusBar(): Promise<void> {
  if (!isNative()) return

  try {
    const { StatusBar } = await import("@capacitor/status-bar")
    await StatusBar.show()
  } catch {
    // Status bar should never break the app
  }
}

/**
 * Hide the status bar.
 */
export async function hideStatusBar(): Promise<void> {
  if (!isNative()) return

  try {
    const { StatusBar } = await import("@capacitor/status-bar")
    await StatusBar.hide()
  } catch {
    // Status bar should never break the app
  }
}
