/**
 * Haptic Feedback Utilities
 *
 * Provides haptic feedback on native platforms (iOS/Android).
 * All functions are no-ops on web — safe to call unconditionally.
 *
 * Uses lazy dynamic imports for Capacitor plugins to avoid
 * bundling native-only code in the web build.
 */

import { isNative } from "./platform"

export type HapticStyle = "light" | "medium" | "heavy"
export type HapticNotificationType = "success" | "warning" | "error"

/**
 * Trigger an impact haptic feedback.
 *
 * @param style - Impact intensity: "light", "medium", or "heavy" (default: "medium")
 */
export async function triggerImpact(
  style: HapticStyle = "medium",
): Promise<void> {
  if (!isNative()) return

  try {
    const { Haptics, ImpactStyle } = await import("@capacitor/haptics")
    const styleMap: Record<HapticStyle, (typeof ImpactStyle)[keyof typeof ImpactStyle]> = {
      light: ImpactStyle.Light,
      medium: ImpactStyle.Medium,
      heavy: ImpactStyle.Heavy,
    }
    await Haptics.impact({ style: styleMap[style] })
  } catch {
    // Haptics should never break the app
  }
}

/**
 * Trigger a notification haptic feedback.
 *
 * @param type - Notification type: "success", "warning", or "error" (default: "success")
 */
export async function triggerNotification(
  type: HapticNotificationType = "success",
): Promise<void> {
  if (!isNative()) return

  try {
    const { Haptics, NotificationType } = await import("@capacitor/haptics")
    const typeMap: Record<
      HapticNotificationType,
      (typeof NotificationType)[keyof typeof NotificationType]
    > = {
      success: NotificationType.Success,
      warning: NotificationType.Warning,
      error: NotificationType.Error,
    }
    await Haptics.notification({ type: typeMap[type] })
  } catch {
    // Haptics should never break the app
  }
}
