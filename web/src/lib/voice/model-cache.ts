/**
 * Whisper model cache management.
 *
 * Wraps @remotion/whisper-web's built-in model download and storage
 * (IndexedDB-backed) with a simplified interface for our UI layer.
 */

import {
  downloadWhisperModel,
  getLoadedModels,
  deleteModel as remotionDeleteModel,
} from "@remotion/whisper-web"
import { MODEL_MAP, WHISPER_MODELS, type WhisperModelSize } from "./model-constants"

export interface ModelCacheStatus {
  isCached: boolean
  modelSize: WhisperModelSize | null
  modelName: string | null
}

export type ProgressCallback = (percent: number) => void

/**
 * Download a Whisper model via @remotion/whisper-web.
 * The library stores models in IndexedDB automatically.
 */
export async function downloadModel(
  size: WhisperModelSize,
  onProgress?: ProgressCallback,
): Promise<void> {
  const model = MODEL_MAP[size]

  await downloadWhisperModel({
    model,
    onProgress: (p) => {
      const pct = Math.round(p.progress * 100)
      onProgress?.(pct)
    },
  })
}

/**
 * Check if a model is cached (downloaded) via @remotion/whisper-web.
 */
export async function isModelCached(size: WhisperModelSize): Promise<boolean> {
  try {
    const loaded = await getLoadedModels()
    const model = MODEL_MAP[size]
    return loaded.includes(model)
  } catch {
    return false
  }
}

/**
 * Get info about the currently cached model.
 * Returns the first cached model found (checks tiny before base).
 */
export async function getCachedModelInfo(): Promise<ModelCacheStatus> {
  try {
    const loaded = await getLoadedModels()
    if (loaded.length === 0) {
      return { isCached: false, modelSize: null, modelName: null }
    }

    // Find which of our model sizes is cached
    for (const size of ["tiny", "base"] as WhisperModelSize[]) {
      const model = MODEL_MAP[size]
      if (loaded.includes(model)) {
        return {
          isCached: true,
          modelSize: size,
          modelName: WHISPER_MODELS[size].displayName,
        }
      }
    }

    return { isCached: false, modelSize: null, modelName: null }
  } catch {
    return { isCached: false, modelSize: null, modelName: null }
  }
}

/**
 * Delete a cached model via @remotion/whisper-web.
 */
export async function deleteModelFromCache(size: WhisperModelSize): Promise<void> {
  const model = MODEL_MAP[size]
  await remotionDeleteModel(model)
}
