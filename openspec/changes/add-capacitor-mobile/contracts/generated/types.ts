/**
 * Generated TypeScript interfaces for add-capacitor-mobile
 *
 * These types define the shared contracts between work packages.
 * Frontend packages import from this file to ensure type consistency.
 *
 * DO NOT EDIT MANUALLY — regenerate from contracts/openapi/capacitor-mobile.yaml
 */

// ─── Platform Detection ────────────────────────────────────────────────────────

/** Capacitor platform identifiers */
export type Platform = "ios" | "android" | "web"

/** Platform detection utilities contract */
export interface PlatformUtils {
  /** Whether running in a native Capacitor shell */
  isNative(): boolean
  /** Current platform: ios, android, or web */
  getPlatform(): Platform
}

/** React hook return type for platform detection */
export interface UsePlatformResult {
  platform: Platform
  isNative: boolean
  isIOS: boolean
  isAndroid: boolean
}

// ─── Share Target ──────────────────────────────────────────────────────────────

/** Shared URL received from native share sheet */
export interface SharedURL {
  /** The URL to save (validated: http/https only, max 2048 chars) */
  url: string
  /** Optional title from share metadata */
  title?: string
  /** Source identifier for the save-url API */
  source: "native-share"
}

/** Offline share queue entry */
export interface PendingShare {
  /** Normalized URL string (for dedup) */
  url: string
  /** ISO timestamp when queued */
  queuedAt: string
  /** Number of retry attempts */
  retryCount: number
}

/** Share handler result */
export interface ShareResult {
  success: boolean
  contentId?: string
  error?: string
  queued?: boolean
}

// ─── Push Notifications (Foreground MVP) ────────────────────────────────────────

/** Device registration request shape (matches backend API) */
export interface DeviceRegistrationRequest {
  platform: "ios" | "android"
  token: string
  delivery_method: "push"
}

/** Device registration response shape (matches backend API) */
export interface DeviceRegistrationResponse {
  id: string
  platform: string
  token: string
  delivery_method: string
  created_at: string
  last_seen: string
}

/** Push notification permission state */
export type PushPermissionState = "prompt" | "granted" | "denied"

/** Local notification from SSE event */
export interface LocalNotification {
  id: string
  title: string
  body: string
  /** Deep link URL for notification tap */
  url?: string
}

// ─── Native STT Engine ─────────────────────────────────────────────────────────

/**
 * NativeSTTEngine contract — must implement STTEngine interface from
 * web/src/lib/voice/engine.ts with id="native"
 *
 * Engine ID: "native"
 * Plugin: @capacitor-community/speech-recognition
 * Availability: only when isNative() returns true
 */
export interface NativeSTTEngineConfig {
  /** BCP-47 language tag, defaults to device locale */
  language?: string
  /** Keep listening after pauses */
  continuous?: boolean
}

// ─── Haptic Feedback ───────────────────────────────────────────────────────────

/** Haptic feedback styles matching Capacitor HapticsImpactStyle */
export type HapticStyle = "light" | "medium" | "heavy"

/** Haptic notification type */
export type HapticNotificationType = "success" | "warning" | "error"

/** Haptic feedback utility contract */
export interface HapticUtils {
  /** Trigger impact haptic (no-op on web) */
  impact(style?: HapticStyle): Promise<void>
  /** Trigger notification haptic (no-op on web) */
  notification(type?: HapticNotificationType): Promise<void>
}

// ─── Status Bar ────────────────────────────────────────────────────────────────

/** Status bar style matching theme */
export type StatusBarStyle = "dark" | "light"

// ─── Save URL API (consumed, not modified) ─────────────────────────────────────

/** Save URL request (matches backend SaveURLRequest) */
export interface SaveURLRequest {
  url: string
  title?: string
  excerpt?: string
  tags?: string[]
  notes?: string
  source?: string
}

/** Save URL response (matches backend SaveURLResponse) */
export interface SaveURLResponse {
  content_id: string
  status: "queued" | "duplicate"
  message: string
  duplicate: boolean
}
