/**
 * STT Engine Interface
 *
 * Abstraction for speech-to-text engines. Each engine implements this interface
 * to provide a consistent API for voice input regardless of the underlying
 * technology (browser, on-device, cloud, native).
 */

export interface TranscriptEvent {
  /** The transcript text */
  text: string
  /** Whether this is a final or interim result */
  isFinal: boolean
  /** Whether the text has been cleaned by the provider (e.g., Gemini with cleanup prompt) */
  cleaned: boolean
  /** Confidence score (0-1), if available */
  confidence?: number
}

export interface STTEngineEvents {
  onResult: (event: TranscriptEvent) => void
  onError: (error: string) => void
  onStateChange: (state: STTEngineState) => void
}

export type STTEngineState = "idle" | "starting" | "listening" | "reconnecting" | "error"

export interface STTEngine {
  /** Unique engine identifier */
  readonly id: "browser" | "cloud" | "native" | "on-device"
  /** Human-readable name */
  readonly name: string
  /** Whether this engine is available in the current environment */
  isAvailable(): boolean | Promise<boolean>
  /** Start listening for voice input */
  start(options: STTStartOptions): void
  /** Stop listening */
  stop(): void
  /** Clean up resources */
  destroy(): void
}

export interface STTStartOptions {
  /** BCP-47 language tag (e.g., "en-US") or "auto" */
  language?: string
  /** Whether to keep listening after pauses */
  continuous?: boolean
  /** Event handlers */
  events: STTEngineEvents
}
