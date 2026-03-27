/**
 * On-Device STT Engine
 *
 * Implements the STTEngine interface using Whisper WASM running in a
 * Web Worker. Provides private, offline-capable speech-to-text by
 * recording audio via MediaRecorder and transcribing locally.
 */

import type { STTEngine, STTEngineEvents, STTEngineState, STTStartOptions } from "./engine"
import { AudioRecorder } from "./audio-recorder"
import { isModelCached } from "./model-cache"
import { MODEL_MAP, type WhisperModelSize } from "./model-constants"
import type { WorkerOutMessage } from "./whisper-worker"

export interface OnDeviceSTTConfig {
  /** Default model size to use */
  defaultModelSize?: WhisperModelSize
}

export class OnDeviceSTTEngine implements STTEngine {
  readonly id = "on-device" as const
  readonly name = "On-Device (Whisper)"

  private config: OnDeviceSTTConfig
  private recorder: AudioRecorder
  private worker: Worker | null = null
  private modelLoaded = false
  private events: STTEngineEvents | null = null
  private state: STTEngineState = "idle"
  private currentLanguage = "en"

  constructor(config: OnDeviceSTTConfig = {}) {
    this.config = config
    this.recorder = new AudioRecorder()
  }

  async isAvailable(): Promise<boolean> {
    // Check WebAssembly support
    if (typeof WebAssembly === "undefined") return false

    // Check MediaRecorder support
    if (typeof MediaRecorder === "undefined") return false

    // Check if a model is cached
    const modelSize = this.config.defaultModelSize ?? "tiny"
    return isModelCached(modelSize)
  }

  start(options: STTStartOptions): void {
    this.events = options.events
    this.setState("starting")

    this.initAndRecord(options.language ?? "en").catch((error) => {
      this.events?.onError(error instanceof Error ? error.message : String(error))
      this.setState("error")
    })
  }

  stop(): void {
    if (this.state !== "listening") return

    this.stopAndTranscribe().catch((error) => {
      this.events?.onError(error instanceof Error ? error.message : String(error))
      this.setState("error")
    })
  }

  destroy(): void {
    this.recorder.destroy()
    if (this.worker) {
      this.worker.terminate()
      this.worker = null
    }
    this.modelLoaded = false
    this.events = null
    this.state = "idle"
  }

  // --- Private methods ---

  private async initAndRecord(language: string): Promise<void> {
    this.currentLanguage = language
    // Initialize worker if not already done
    if (!this.worker) {
      await this.initWorker()
    }

    // Load model if not already loaded
    if (!this.modelLoaded) {
      await this.loadModel()
    }

    // Start recording
    await this.recorder.startRecording({ sampleRate: 16000, channelCount: 1 })
    this.setState("listening")
  }

  private async stopAndTranscribe(): Promise<void> {
    // Stop recording and get audio buffer
    const audio = await this.recorder.stopRecording()

    // Show processing state while transcribing
    this.setState("starting") // Reuse "starting" for processing indication

    // Send to worker for transcription
    this.worker?.postMessage({ type: "transcribe", audio, language: this.currentLanguage })
  }

  private initWorker(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.worker = new Worker(
          new URL("./whisper-worker.ts", import.meta.url),
          { type: "module" }
        )

        const onReady = (event: MessageEvent<WorkerOutMessage>) => {
          if (event.data.type === "ready") {
            this.worker?.removeEventListener("message", onReady)
            // Register persistent handler AFTER ready — avoids duplicate handling
            this.worker?.addEventListener("message", (e: MessageEvent<WorkerOutMessage>) => {
              this.handleWorkerMessage(e.data)
            })
            resolve()
          }
        }

        this.worker.addEventListener("message", onReady)
        this.worker.addEventListener("error", (e) => reject(e.error ?? e.message))
      } catch (e) {
        reject(e)
      }
    })
  }

  private async loadModel(): Promise<void> {
    const modelSize = this.config.defaultModelSize ?? "tiny"
    const whisperModel = MODEL_MAP[modelSize]

    return new Promise((resolve, reject) => {
      const onMessage = (event: MessageEvent<WorkerOutMessage>) => {
        if (event.data.type === "model-loaded") {
          this.worker?.removeEventListener("message", onMessage)
          this.modelLoaded = true
          resolve()
        } else if (event.data.type === "model-error") {
          this.worker?.removeEventListener("message", onMessage)
          reject(new Error(event.data.error))
        }
      }

      this.worker?.addEventListener("message", onMessage)
      this.worker?.postMessage({ type: "load-model", model: whisperModel })
    })
  }

  private handleWorkerMessage(msg: WorkerOutMessage): void {
    switch (msg.type) {
      case "transcription-result":
        this.events?.onResult({
          text: msg.text,
          isFinal: true,
          cleaned: false,
          confidence: msg.confidence,
        })
        this.setState("idle")
        break

      case "transcription-error":
        this.events?.onError(msg.error)
        this.setState("error")
        break

      // model-loading, model-loaded, model-error handled in loadModel()
      // ready handled in initWorker()
    }
  }

  private setState(state: STTEngineState): void {
    this.state = state
    this.events?.onStateChange(state)
  }
}
