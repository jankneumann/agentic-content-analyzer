/**
 * STT Engine Interface Contract
 *
 * The NativeSTTEngine (wp-native-stt) MUST implement this interface
 * from web/src/lib/voice/engine.ts. This contract is a snapshot of the
 * existing interface for verification — the source of truth remains engine.ts.
 *
 * Integration point: AutoSTTEngine (wp-native-stt task 7.3) registers
 * the NativeSTTEngine in its engines map with key "native".
 */

export interface TranscriptEvent {
  text: string
  isFinal: boolean
  cleaned: boolean
  confidence?: number
}

export interface STTEngineEvents {
  onResult: (event: TranscriptEvent) => void
  onError: (error: string) => void
  onStateChange: (state: STTEngineState) => void
}

export type STTEngineState =
  | "idle"
  | "starting"
  | "listening"
  | "reconnecting"
  | "error"

export interface STTEngine {
  readonly id: "browser" | "cloud" | "native" | "on-device"
  readonly name: string
  isAvailable(): boolean | Promise<boolean>
  start(options: STTStartOptions): void
  stop(): void
  destroy(): void
}

export interface STTStartOptions {
  language?: string
  continuous?: boolean
  events: STTEngineEvents
}
