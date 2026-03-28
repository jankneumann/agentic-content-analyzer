/**
 * Platform Detection Hook
 *
 * Provides reactive platform information for React components.
 * Values are stable (platform doesn't change at runtime) so no state needed.
 */

import { useMemo } from "react"
import { getPlatform, isNative, isTauri, type Platform } from "@/lib/platform"

export interface UsePlatformResult {
  platform: Platform
  isNative: boolean
  isTauri: boolean
  isDesktop: boolean
  isIOS: boolean
  isAndroid: boolean
}

/**
 * React hook that returns platform detection results.
 *
 * All values are derived from static platform detection
 * and are stable for the lifetime of the app.
 */
export function usePlatform(): UsePlatformResult {
  return useMemo(() => {
    const platform = getPlatform()
    const tauri = isTauri()
    return {
      platform,
      isNative: isNative(),
      isTauri: tauri,
      isDesktop: tauri,
      isIOS: platform === "ios",
      isAndroid: platform === "android",
    }
  }, [])
}
