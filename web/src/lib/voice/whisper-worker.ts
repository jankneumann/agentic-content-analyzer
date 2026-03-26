/**
 * Whisper WASM Web Worker
 *
 * Runs Whisper model loading and inference off the main thread.
 * Communicates via typed postMessage protocol.
 *
 * The actual WASM binding is deferred to integration time — this worker
 * currently stores the raw model bytes and stubs out transcription.
 * When a Whisper WASM package is integrated, the `transcribe` handler
 * will be updated to call into it.
 */

// ---------------------------------------------------------------------------
// Message types (re-exported so callers can import from the same module)
// ---------------------------------------------------------------------------

export type WorkerInMessage =
  | { type: "load-model"; modelBytes: ArrayBuffer }
  | { type: "transcribe"; audio: Float32Array; language: string }
  | { type: "unload-model" };

export type WorkerOutMessage =
  | { type: "model-loading"; progress: number }
  | { type: "model-loaded" }
  | { type: "model-error"; error: string }
  | { type: "transcription-result"; text: string; confidence?: number }
  | { type: "transcription-error"; error: string }
  | { type: "ready" };

// ---------------------------------------------------------------------------
// Worker-scoped state
// ---------------------------------------------------------------------------

/** Raw GGML model bytes kept in memory while the model is "loaded". */
let modelBytes: ArrayBuffer | null = null;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function post(msg: WorkerOutMessage): void {
  self.postMessage(msg);
}

function toErrorString(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

// ---------------------------------------------------------------------------
// Message handler
// ---------------------------------------------------------------------------

self.onmessage = (event: MessageEvent<WorkerInMessage>) => {
  const msg = event.data;

  switch (msg.type) {
    case "load-model":
      handleLoadModel(msg.modelBytes);
      break;
    case "transcribe":
      handleTranscribe(msg.audio, msg.language);
      break;
    case "unload-model":
      handleUnloadModel();
      break;
    default:
      // Exhaustiveness guard — if a new message type is added but not
      // handled, TypeScript will flag this at compile time.
      post({
        type: "transcription-error",
        error: `Unknown message type: ${(msg as { type: string }).type}`,
      });
  }
};

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

function handleLoadModel(bytes: ArrayBuffer): void {
  try {
    post({ type: "model-loading", progress: 0 });

    // Store raw bytes. Actual WASM initialisation will happen here once
    // a Whisper WASM package is integrated.
    modelBytes = bytes;

    post({ type: "model-loading", progress: 100 });
    post({ type: "model-loaded" });
  } catch (err) {
    modelBytes = null;
    post({ type: "model-error", error: toErrorString(err) });
  }
}

function handleTranscribe(audio: Float32Array, language: string): void {
  try {
    if (!modelBytes) {
      post({
        type: "transcription-error",
        error: "No model loaded. Send a load-model message first.",
      });
      return;
    }

    // -----------------------------------------------------------------
    // STUB: Real WASM inference will replace this block.
    // For now we acknowledge that transcription was requested so the
    // calling code can exercise the full message round-trip.
    // -----------------------------------------------------------------
    void language; // suppress unused-variable lint
    void audio;

    post({
      type: "transcription-result",
      text: "",
      confidence: undefined,
    });
  } catch (err) {
    post({ type: "transcription-error", error: toErrorString(err) });
  }
}

function handleUnloadModel(): void {
  modelBytes = null;
}

// ---------------------------------------------------------------------------
// Signal readiness
// ---------------------------------------------------------------------------

post({ type: "ready" });
