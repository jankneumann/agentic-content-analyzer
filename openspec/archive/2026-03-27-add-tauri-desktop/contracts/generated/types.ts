/**
 * Generated types for add-tauri-desktop feature
 * These types define the interfaces between work packages.
 */

// ── Platform Detection (wp-platform) ──────────────────────

/** Supported platform identifiers */
export type Platform = 'desktop' | 'web';
// Note: 'ios' | 'android' added by add-capacitor-mobile

/** Check if running inside Tauri shell */
export declare function isTauri(): boolean;

/** Get current platform identifier */
export declare function getPlatform(): Platform;

// ── File Drop (wp-drag-drop) ──────────────────────────────

/** Supported file extensions for drag-and-drop */
export type SupportedFileExtension =
  | '.pdf' | '.docx' | '.pptx' | '.xlsx'
  | '.txt' | '.md' | '.html' | '.epub'
  | '.wav' | '.mp3' | '.msg';

/** Result of file validation before upload */
export interface FileDropValidation {
  file: string;           // Full file path
  fileName: string;       // File name only
  extension: string;      // File extension
  sizeBytes: number;      // File size in bytes
  status: 'valid' | 'unsupported' | 'oversized';
  error?: string;         // Human-readable error message
}

/** Summary of a multi-file drop operation */
export interface FileDropSummary {
  total: number;
  uploaded: number;
  rejected: number;      // unsupported + oversized
  failed: number;        // upload failures
  results: FileDropResult[];
}

export interface FileDropResult {
  fileName: string;
  status: 'uploaded' | 'unsupported' | 'oversized' | 'upload_failed';
  error?: string;
}

// ── System Tray (wp-tray-shortcut) ────────────────────────

/** Tray context menu actions */
export type TrayAction = 'open_app' | 'ingest_url' | 'start_voice' | 'quit';

/** Tray menu event from Rust backend */
export interface TrayMenuEvent {
  action: TrayAction;
  payload?: string;       // URL for ingest_url action
}

// ── Global Shortcut (wp-tray-shortcut) ────────────────────

/** Default shortcut bindings per platform */
export interface ShortcutConfig {
  macos: string;          // 'Cmd+Shift+Space'
  windows: string;        // 'Ctrl+Shift+Space'
  linux: string;          // 'Ctrl+Shift+Space'
}

/** Shortcut registration result */
export interface ShortcutRegistration {
  registered: boolean;
  shortcut: string;
  error?: string;         // If registration failed
}

// ── Desktop Notifications (wp-notifications) ───────────────

/** SSE notification event from backend */
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

/** Notification connection state */
export type NotificationConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'disabled';       // SSE endpoint unavailable, graceful degradation

// ── Voice Overlay (wp-tray-shortcut) ───────────────────────

/** Voice overlay panel state */
export interface VoiceOverlayState {
  visible: boolean;
  alwaysOnTop: boolean;
  transcript: string;
  interimTranscript: string;
  isListening: boolean;
}
