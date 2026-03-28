/**
 * Desktop Notification Manager
 *
 * Subscribes to backend SSE event stream and delivers native desktop
 * notifications via Tauri's notification plugin.
 *
 * Graceful degradation: if the SSE endpoint is unavailable (non-200,
 * connection refused), notifications are disabled silently with a
 * console warning — no user-facing error.
 */

export type NotificationConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'disabled';

export interface NotificationEvent {
  id: string;
  type: string;
  title: string;
  summary: string;
  payload: {
    url?: string;
  };
  timestamp: string;
}

type StateChangeCallback = (state: NotificationConnectionState) => void;
type NotificationCallback = (event: NotificationEvent) => void;

const SSE_ENDPOINT = '/api/v1/notifications/stream';
const RECONNECT_DELAY_MS = 5000;
const MAX_RECONNECT_ATTEMPTS = 5;

/**
 * Check if we're running in a Tauri context
 */
function isTauriContext(): boolean {
  return typeof window !== 'undefined' && Boolean((window as any).__TAURI_INTERNALS__);
}

/**
 * Desktop notification manager that connects to the backend SSE stream
 * and delivers native notifications via Tauri.
 */
export class DesktopNotificationManager {
  private eventSource: EventSource | null = null;
  private state: NotificationConnectionState = 'disconnected';
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private lastEventId: string | null = null;
  private onStateChange: StateChangeCallback | null = null;
  private onNotification: NotificationCallback | null = null;
  private permissionGranted = false;

  /**
   * Initialize notifications — request permission and connect to SSE.
   */
  async init(
    onStateChange?: StateChangeCallback,
    onNotification?: NotificationCallback,
  ): Promise<void> {
    if (!isTauriContext()) return;

    this.onStateChange = onStateChange || null;
    this.onNotification = onNotification || null;

    // Request notification permission
    try {
      const { isPermissionGranted, requestPermission } = await import(
        '@tauri-apps/plugin-notification'
      );
      this.permissionGranted = await isPermissionGranted();
      if (!this.permissionGranted) {
        const permission = await requestPermission();
        this.permissionGranted = permission === 'granted';
      }
    } catch (err) {
      console.warn('[notifications] Failed to request permission:', err);
    }

    this.connect();
  }

  /**
   * Connect to the SSE endpoint with graceful degradation.
   */
  private connect(): void {
    this.setState('connecting');

    try {
      const url = this.lastEventId
        ? `${SSE_ENDPOINT}?lastEventId=${encodeURIComponent(this.lastEventId)}`
        : SSE_ENDPOINT;

      this.eventSource = new EventSource(url);

      this.eventSource.onopen = () => {
        this.reconnectAttempts = 0;
        this.setState('connected');
      };

      this.eventSource.onmessage = (event) => {
        this.handleMessage(event);
      };

      this.eventSource.onerror = () => {
        this.eventSource?.close();
        this.eventSource = null;

        if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
          // Graceful degradation: disable silently
          console.warn(
            '[notifications] SSE endpoint unavailable after',
            MAX_RECONNECT_ATTEMPTS,
            'attempts — disabling notifications',
          );
          this.setState('disabled');
          return;
        }

        this.setState('disconnected');
        this.reconnectAttempts++;
        this.reconnectTimer = setTimeout(
          () => this.connect(),
          RECONNECT_DELAY_MS * this.reconnectAttempts,
        );
      };
    } catch (err) {
      // Connection refused or network error — graceful degradation
      console.warn('[notifications] Failed to connect to SSE:', err);
      this.setState('disabled');
    }
  }

  /**
   * Handle incoming SSE messages
   */
  private async handleMessage(event: MessageEvent): Promise<void> {
    try {
      if (event.lastEventId) {
        this.lastEventId = event.lastEventId;
      }

      const data: NotificationEvent = JSON.parse(event.data);
      this.onNotification?.(data);

      // Show native notification
      if (this.permissionGranted) {
        try {
          const { sendNotification } = await import(
            '@tauri-apps/plugin-notification'
          );
          sendNotification({
            title: data.title,
            body: data.summary,
          });
        } catch (err) {
          console.warn('[notifications] Failed to send notification:', err);
        }
      }
    } catch (err) {
      console.warn('[notifications] Failed to parse SSE message:', err);
    }
  }

  /**
   * Handle notification click — show/focus window and navigate
   */
  async handleNotificationClick(url?: string): Promise<void> {
    if (!isTauriContext()) return;

    try {
      const { getCurrentWebviewWindow } = await import(
        '@tauri-apps/api/webviewWindow'
      );
      const appWindow = getCurrentWebviewWindow();
      await appWindow.show();
      await appWindow.setFocus();

      if (url) {
        // Navigate within the SPA
        window.location.hash = url;
      }
    } catch (err) {
      console.warn('[notifications] Failed to focus window:', err);
    }
  }

  private setState(state: NotificationConnectionState): void {
    this.state = state;
    this.onStateChange?.(state);
  }

  getState(): NotificationConnectionState {
    return this.state;
  }

  /**
   * Disconnect and clean up
   */
  destroy(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.eventSource?.close();
    this.eventSource = null;
    this.setState('disconnected');
  }
}

// Singleton instance
let manager: DesktopNotificationManager | null = null;

export function getNotificationManager(): DesktopNotificationManager {
  if (!manager) {
    manager = new DesktopNotificationManager();
  }
  return manager;
}
