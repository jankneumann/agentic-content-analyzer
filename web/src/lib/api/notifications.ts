/**
 * Notification API Functions
 *
 * API calls for notification events, unread count, mark-read, and preferences.
 */

import { apiClient, API_BASE_URL } from "./client"
import type {
  NotificationEventListResponse,
  UnreadCountResponse,
  NotificationPreferencesResponse,
} from "@/types"

/** Fetch notification events with optional filters */
export async function fetchNotificationEvents(params?: {
  page?: number
  page_size?: number
  type?: string
  since?: string
}): Promise<NotificationEventListResponse> {
  return apiClient.get<NotificationEventListResponse>("/notifications/events", {
    params: params as Record<string, string | number | boolean | undefined>,
  })
}

/** Fetch unread notification count */
export async function fetchUnreadCount(): Promise<UnreadCountResponse> {
  return apiClient.get<UnreadCountResponse>("/notifications/unread-count")
}

/** Mark a single event as read */
export async function markEventRead(eventId: string): Promise<void> {
  await apiClient.put(`/notifications/events/${eventId}/read`)
}

/** Mark all events as read */
export async function markAllEventsRead(): Promise<void> {
  await apiClient.put("/notifications/events/read-all")
}

/** Fetch notification preferences */
export async function fetchNotificationPreferences(): Promise<NotificationPreferencesResponse> {
  return apiClient.get<NotificationPreferencesResponse>("/settings/notifications")
}

/** Update a notification preference */
export async function updateNotificationPreference(
  eventType: string,
  enabled: boolean
): Promise<void> {
  await apiClient.put(`/settings/notifications/${eventType}`, { enabled })
}

/** Reset a notification preference to default */
export async function resetNotificationPreference(eventType: string): Promise<void> {
  await apiClient.delete(`/settings/notifications/${eventType}`)
}

/**
 * Create an SSE connection for real-time notification events.
 *
 * Returns an EventSource that emits "notification" events.
 * The caller is responsible for closing the connection.
 */
export function createNotificationSSE(): EventSource {
  const url = `${API_BASE_URL}/notifications/stream`
  return new EventSource(url, { withCredentials: true })
}
