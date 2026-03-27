/**
 * Whisper model constants.
 *
 * Uses @remotion/whisper-web model names and sizes.
 * The library manages its own model storage via IndexedDB.
 */

import type { WhisperWebModel } from "@remotion/whisper-web"

export type WhisperModelSize = "tiny" | "base"

/** Maps our simplified size names to @remotion/whisper-web model identifiers */
export const MODEL_MAP: Record<WhisperModelSize, WhisperWebModel> = {
  tiny: "tiny.en",
  base: "base.en",
}

export interface WhisperModelInfo {
  size: WhisperModelSize
  whisperWebModel: WhisperWebModel
  displayName: string
  fileSize: number // bytes (approximate)
  memoryEstimate: number // bytes during inference
}

export const WHISPER_MODELS: Record<WhisperModelSize, WhisperModelInfo> = {
  tiny: {
    size: "tiny",
    whisperWebModel: "tiny.en",
    displayName: "Tiny (English)",
    fileSize: 39_000_000, // ~39MB
    memoryEstimate: 200_000_000, // ~200MB
  },
  base: {
    size: "base",
    whisperWebModel: "base.en",
    displayName: "Base (English)",
    fileSize: 74_000_000, // ~74MB
    memoryEstimate: 500_000_000, // ~500MB
  },
}
