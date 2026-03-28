/**
 * React hook for desktop notifications via Tauri
 *
 * Initializes SSE connection on mount (only in Tauri context).
 * Returns connection state for optional UI indicators.
 */

import { useEffect, useState } from 'react';
import {
  getNotificationManager,
  type NotificationConnectionState,
  type NotificationEvent,
} from '@/lib/tauri/notifications';

interface UseDesktopNotificationsOptions {
  enabled?: boolean;
  onNotification?: (event: NotificationEvent) => void;
}

interface UseDesktopNotificationsResult {
  connectionState: NotificationConnectionState;
  isConnected: boolean;
  isDisabled: boolean;
}

/**
 * Check if running in Tauri context
 */
function isTauriContext(): boolean {
  return typeof window !== 'undefined' && Boolean((window as any).__TAURI_INTERNALS__);
}

export function useDesktopNotifications(
  options: UseDesktopNotificationsOptions = {},
): UseDesktopNotificationsResult {
  const { enabled = true, onNotification } = options;
  const [connectionState, setConnectionState] =
    useState<NotificationConnectionState>('disconnected');

  useEffect(() => {
    if (!enabled || !isTauriContext()) return;

    const manager = getNotificationManager();
    manager.init(setConnectionState, onNotification);

    return () => {
      manager.destroy();
    };
  }, [enabled, onNotification]);

  return {
    connectionState,
    isConnected: connectionState === 'connected',
    isDisabled: connectionState === 'disabled',
  };
}
