/**
 * Contract type definitions for on-device STT feature.
 *
 * These interfaces define the boundaries between work packages.
 * Implementations MUST conform to these signatures.
 *
 * NOTE: STTEngine, TranscriptEvent, STTEngineEvents, STTEngineState,
 * and STTStartOptions already exist in web/src/lib/voice/engine.ts.
 * This file defines ONLY the new types introduced by this feature.
 */

// --- Worker Message Protocol (wp-whisper-worker ↔ wp-engine) ---

/** Messages sent FROM main thread TO worker */
export type WorkerInMessage =
  | { type: "load-model"; modelUrl: string; modelSize: WhisperModelSize }
  | { type: "transcribe"; audio: Float32Array; language: string }
  | { type: "unload-model" };

/** Messages sent FROM worker TO main thread */
export type WorkerOutMessage =
  | { type: "model-loading"; progress: number } // 0-100
  | { type: "model-loaded"; modelSize: WhisperModelSize }
  | { type: "model-error"; error: string }
  | { type: "transcription-result"; text: string; confidence?: number }
  | { type: "transcription-error"; error: string }
  | { type: "ready" };

// --- Model Management (wp-model-cache) ---

export type WhisperModelSize = "tiny" | "base";

export interface WhisperModelInfo {
  size: WhisperModelSize;
  name: string; // e.g., "ggml-tiny.en.bin"
  fileSize: number; // bytes
  memoryEstimate: number; // bytes during inference
  cdnUrl: string;
}

export interface ModelCacheStatus {
  isCached: boolean;
  modelSize: WhisperModelSize | null;
  modelName: string | null;
  cachedAt: string | null; // ISO-8601
}

/** Interface for wp-model-cache implementation */
export interface ModelCacheOperations {
  downloadModel(
    size: WhisperModelSize,
    onProgress?: (progress: number) => void
  ): Promise<ArrayBuffer>;
  isModelCached(size: WhisperModelSize): Promise<boolean>;
  getCachedModel(size: WhisperModelSize): Promise<ArrayBuffer | null>;
  getCachedModelInfo(): Promise<ModelCacheStatus>;
  deleteModel(size: WhisperModelSize): Promise<void>;
}

// --- Audio Recording (wp-audio) ---

export interface AudioRecorderOptions {
  sampleRate?: number; // default: 16000
  channelCount?: number; // default: 1 (mono)
}

/** Interface for wp-audio implementation */
export interface AudioRecorderOperations {
  requestPermission(): Promise<boolean>;
  startRecording(options?: AudioRecorderOptions): Promise<void>;
  stopRecording(): Promise<Float32Array>;
  isRecording(): boolean;
  destroy(): void;
}

// --- On-Device Engine (wp-engine) ---

/**
 * OnDeviceSTTEngine implements the existing STTEngine interface
 * from web/src/lib/voice/engine.ts with id = "on-device".
 *
 * Constructor signature:
 *   new OnDeviceSTTEngine(config?: { defaultModelSize?: WhisperModelSize })
 *
 * isAvailable() checks:
 *   1. WebAssembly support (typeof WebAssembly !== "undefined")
 *   2. Model is cached (via ModelCacheOperations.isModelCached())
 *   3. MediaRecorder available (typeof MediaRecorder !== "undefined")
 *
 * start() flow:
 *   1. Set state "starting"
 *   2. Start audio recording via AudioRecorder
 *   3. Set state "listening"
 *   4. On stop: get audio buffer, send to Whisper worker
 *   5. Emit TranscriptEvent with cleaned=false
 *   6. Set state "idle"
 */

// --- Backend Settings Extension (wp-settings) ---

/** New settings fields added to voice settings API */
export interface OnDeviceSTTSettings {
  stt_engine: "auto" | "browser" | "cloud" | "on-device";
  stt_model_size: WhisperModelSize;
}

// --- Settings UI Types (wp-settings-ui) ---

export interface ModelDownloadState {
  isDownloading: boolean;
  progress: number; // 0-100
  error: string | null;
}
