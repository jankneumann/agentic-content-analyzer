/**
 * Notification Hooks
 *
 * React Query hooks for notification events, unread count, SSE subscription,
 * and notification preferences.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useRef } from "react"

import {
  fetchNotificationEvents,
  fetchUnreadCount,
  markEventRead,
  markAllEventsRead,
  createNotificationSSE,
  fetchNotificationPreferences,
  updateNotificationPreference,
  resetNotificationPreference,
} from "@/lib/api/notifications"
import { notificationKeys } from "@/lib/api/query-keys"
import type { NotificationEvent } from "@/types"

/**
 * Hook for fetching notification events
 */
export function useNotificationEvents(params?: {
  page?: number
  page_size?: number
  type?: string
}) {
  return useQuery({
    queryKey: notificationKeys.eventList(params),
    queryFn: () => fetchNotificationEvents(params),
  })
}

/**
 * Hook for unread notification count
 *
 * Polls every 60 seconds as a fallback when SSE is unavailable.
 */
export function useUnreadCount() {
  return useQuery({
    queryKey: notificationKeys.unreadCount(),
    queryFn: fetchUnreadCount,
    refetchInterval: 60_000,
  })
}

/**
 * Hook for marking a single event as read
 */
export function useMarkEventRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: markEventRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all })
    },
  })
}

/**
 * Hook for marking all events as read
 */
export function useMarkAllRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: markAllEventsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all })
    },
  })
}

/**
 * Hook for SSE subscription to real-time notification events.
 *
 * Automatically connects on mount and reconnects on error.
 * Updates the unread count and event list caches when events arrive.
 */
export function useNotificationSSE(
  onEvent?: (event: NotificationEvent) => void
) {
  const queryClient = useQueryClient()
  const eventSourceRef = useRef<EventSource | null>(null)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    try {
      const es = createNotificationSSE()

      es.addEventListener("notification", (e: MessageEvent) => {
        try {
          const event = JSON.parse(e.data) as NotificationEvent
          // Invalidate queries to refresh unread count and event list
          queryClient.invalidateQueries({
            queryKey: notificationKeys.unreadCount(),
          })
          queryClient.invalidateQueries({
            queryKey: notificationKeys.events(),
          })
          onEventRef.current?.(event)
        } catch {
          // Ignore parse errors
        }
      })

      es.onerror = () => {
        es.close()
        eventSourceRef.current = null
        // Reconnect after 5 seconds
        setTimeout(connect, 5000)
      }

      eventSourceRef.current = es
    } catch {
      // SSE not available, rely on polling
    }
  }, [queryClient])

  useEffect(() => {
    connect()
    return () => {
      eventSourceRef.current?.close()
      eventSourceRef.current = null
    }
  }, [connect])
}

/**
 * Hook for notification preferences
 */
export function useNotificationPreferences() {
  return useQuery({
    queryKey: notificationKeys.preferences(),
    queryFn: fetchNotificationPreferences,
  })
}

/**
 * Hook for updating a notification preference
 */
export function useUpdateNotificationPreference() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ eventType, enabled }: { eventType: string; enabled: boolean }) =>
      updateNotificationPreference(eventType, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: notificationKeys.preferences(),
      })
    },
  })
}

/**
 * Hook for resetting a notification preference
 */
export function useResetNotificationPreference() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: resetNotificationPreference,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: notificationKeys.preferences(),
      })
    },
  })
}
