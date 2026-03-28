/**
 * Whisper WASM Web Worker
 *
 * Runs Whisper model inference off the main thread using @remotion/whisper-web.
 * The library handles WASM loading, model management, and transcription.
 *
 * Communication via typed postMessage protocol.
 */

import { transcribe, downloadWhisperModel } from "@remotion/whisper-web"
import type { WhisperWebModel } from "@remotion/whisper-web"

// ---------------------------------------------------------------------------
// Message types (re-exported so callers can import from the same module)
// ---------------------------------------------------------------------------

export type WorkerInMessage =
  | { type: "load-model"; model: WhisperWebModel }
  | { type: "transcribe"; audio: Float32Array; language: string }
  | { type: "unload-model" }

export type WorkerOutMessage =
  | { type: "model-loading"; progress: number }
  | { type: "model-loaded" }
  | { type: "model-error"; error: string }
  | { type: "transcription-result"; text: string; confidence?: number }
  | { type: "transcription-error"; error: string }
  | { type: "ready" }

// ---------------------------------------------------------------------------
// Worker-scoped state
// ---------------------------------------------------------------------------

let loadedModel: WhisperWebModel | null = null

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function post(msg: WorkerOutMessage): void {
  self.postMessage(msg)
}

function toErrorString(err: unknown): string {
  if (err instanceof Error) return err.message
  return String(err)
}

// ---------------------------------------------------------------------------
// Message handler
// ---------------------------------------------------------------------------

self.onmessage = (event: MessageEvent<WorkerInMessage>) => {
  const msg = event.data

  switch (msg.type) {
    case "load-model":
      void handleLoadModel(msg.model)
      break
    case "transcribe":
      void handleTranscribe(msg.audio, msg.language)
      break
    case "unload-model":
      handleUnloadModel()
      break
    default:
      post({
        type: "transcription-error",
        error: `Unknown message type: ${(msg as { type: string }).type}`,
      })
  }
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

async function handleLoadModel(model: WhisperWebModel): Promise<void> {
  try {
    post({ type: "model-loading", progress: 0 })

    // Ensure model is downloaded (no-op if already cached in IndexedDB)
    await downloadWhisperModel({
      model,
      onProgress: (p) => {
        const pct = Math.round(p.progress * 100)
        post({ type: "model-loading", progress: pct })
      },
    })

    loadedModel = model
    post({ type: "model-loaded" })
  } catch (err) {
    loadedModel = null
    post({ type: "model-error", error: toErrorString(err) })
  }
}

async function handleTranscribe(audio: Float32Array, language: string): Promise<void> {
  try {
    if (!loadedModel) {
      post({
        type: "transcription-error",
        error: "No model loaded. Send a load-model message first.",
      })
      return
    }

    // English-only models (*.en) only support "en" language
    // Force "en" for English models to avoid silent misrecognition
    const isEnglishModel = loadedModel.endsWith(".en")
    const resolvedLanguage = isEnglishModel ? "en" : (language === "auto" ? "auto" : language)

    // Run Whisper inference via @remotion/whisper-web
    const result = await transcribe({
      channelWaveform: audio,
      model: loadedModel,
      language: resolvedLanguage as "en",
      onProgress: () => {
        // Could emit progress but transcription is usually fast
      },
    })

    // Combine all transcription segments into a single string
    const text = result.transcription
      .map((segment) => segment.text.trim())
      .join(" ")
      .trim()

    post({
      type: "transcription-result",
      text,
      confidence: undefined,
    })
  } catch (err) {
    post({ type: "transcription-error", error: toErrorString(err) })
  }
}

function handleUnloadModel(): void {
  loadedModel = null
}

// ---------------------------------------------------------------------------
// Signal readiness
// ---------------------------------------------------------------------------

post({ type: "ready" })
