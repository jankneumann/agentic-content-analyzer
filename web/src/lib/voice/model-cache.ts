import {
  WHISPER_MODELS,
  MODEL_CACHE_NAME,
  type WhisperModelSize,
} from "./model-constants"

export interface ModelCacheStatus {
  isCached: boolean
  modelSize: WhisperModelSize | null
  modelName: string | null
  cachedAt: string | null
}

export type ProgressCallback = (percent: number) => void

/**
 * Download a Whisper model and store it in the Cache API.
 * Tracks download progress via an optional callback (0-100).
 * Cleans up partial cache entries on failure.
 */
export async function downloadModel(
  size: WhisperModelSize,
  onProgress?: ProgressCallback,
): Promise<ArrayBuffer> {
  const modelInfo = WHISPER_MODELS[size]
  const cache = await caches.open(MODEL_CACHE_NAME)

  // Start the fetch
  const response = await fetch(modelInfo.cdnUrl)

  if (!response.ok) {
    throw new Error(
      `Failed to download model ${modelInfo.name}: ${response.status} ${response.statusText}`,
    )
  }

  if (!response.body) {
    throw new Error(
      `Response body is null for model ${modelInfo.name} — streaming not supported`,
    )
  }

  const contentLength =
    Number(response.headers.get("content-length")) || modelInfo.fileSize
  const reader = response.body.getReader()
  const chunks: Uint8Array[] = []
  let receivedBytes = 0

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break

      chunks.push(value)
      receivedBytes += value.byteLength

      if (onProgress) {
        const percent = Math.min(
          100,
          Math.round((receivedBytes / contentLength) * 100),
        )
        onProgress(percent)
      }
    }
  } catch (error) {
    // Clean up any partial cache entry
    await cache.delete(modelInfo.cdnUrl).catch(() => {})
    throw error
  }

  // Combine chunks into a single ArrayBuffer
  const fullArray = new Uint8Array(receivedBytes)
  let offset = 0
  for (const chunk of chunks) {
    fullArray.set(chunk, offset)
    offset += chunk.byteLength
  }

  // Store in Cache API as a synthetic Response
  const cacheResponse = new Response(fullArray.buffer, {
    status: 200,
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Length": String(receivedBytes),
      "X-Cached-At": new Date().toISOString(),
      "X-Model-Size": size,
    },
  })

  await cache.put(modelInfo.cdnUrl, cacheResponse)

  return fullArray.buffer as ArrayBuffer
}

/**
 * Check whether a model of the given size is already cached.
 */
export async function isModelCached(
  size: WhisperModelSize,
): Promise<boolean> {
  try {
    const cache = await caches.open(MODEL_CACHE_NAME)
    const match = await cache.match(WHISPER_MODELS[size].cdnUrl)
    return match !== undefined
  } catch {
    return false
  }
}

/**
 * Retrieve a cached model as an ArrayBuffer, or null if not cached.
 */
export async function getCachedModel(
  size: WhisperModelSize,
): Promise<ArrayBuffer | null> {
  try {
    const cache = await caches.open(MODEL_CACHE_NAME)
    const match = await cache.match(WHISPER_MODELS[size].cdnUrl)
    if (!match) return null
    return await match.arrayBuffer()
  } catch {
    return null
  }
}

/**
 * Inspect the cache and return info about the first cached model found.
 * Checks models in order: tiny, base.
 */
export async function getCachedModelInfo(): Promise<ModelCacheStatus> {
  const sizes: WhisperModelSize[] = ["tiny", "base"]

  try {
    const cache = await caches.open(MODEL_CACHE_NAME)

    for (const size of sizes) {
      const match = await cache.match(WHISPER_MODELS[size].cdnUrl)
      if (match) {
        return {
          isCached: true,
          modelSize: size,
          modelName: WHISPER_MODELS[size].name,
          cachedAt: match.headers.get("X-Cached-At"),
        }
      }
    }
  } catch {
    // Cache API unavailable or error — treat as uncached
  }

  return {
    isCached: false,
    modelSize: null,
    modelName: null,
    cachedAt: null,
  }
}

/**
 * Delete a cached model.
 */
export async function deleteModel(size: WhisperModelSize): Promise<void> {
  const cache = await caches.open(MODEL_CACHE_NAME)
  await cache.delete(WHISPER_MODELS[size].cdnUrl)
}
