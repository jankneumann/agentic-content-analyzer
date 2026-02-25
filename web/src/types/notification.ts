/**
 * Notification event types and API response shapes.
 */

/** Notification event types matching backend enum */
export type NotificationEventType =
  | "batch_summary"
  | "theme_analysis"
  | "digest_creation"
  | "script_generation"
  | "audio_generation"
  | "pipeline_completion"
  | "job_failure"

/** A single notification event */
export interface NotificationEvent {
  id: string
  event_type: NotificationEventType
  title: string
  summary: string | null
  payload: Record<string, unknown>
  read: boolean
  created_at: string
}

/** Paginated notification event list */
export interface NotificationEventListResponse {
  events: NotificationEvent[]
  total: number
  page: number
  page_size: number
}

/** Unread count response */
export interface UnreadCountResponse {
  count: number
}

/** Device registration */
export interface DeviceRegistration {
  id: string
  platform: string
  token: string
  delivery_method: string
  created_at: string
  last_seen: string
}

/** Notification preference for a single event type */
export interface NotificationPreference {
  event_type: NotificationEventType
  description: string
  enabled: boolean
  source: "env" | "db" | "default"
}

/** All notification preferences */
export interface NotificationPreferencesResponse {
  preferences: NotificationPreference[]
}
