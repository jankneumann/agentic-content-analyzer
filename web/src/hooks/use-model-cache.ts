/**
 * Model Cache Hook
 *
 * Wraps the Cache API-based model storage for Whisper ONNX models.
 * Provides reactive state for download progress, cached status, and
 * model management (download/delete).
 */

import { useState, useCallback, useEffect } from "react"
import {
  downloadModel,
  deleteModel,
  getCachedModelInfo,
  type ModelCacheStatus,
} from "../lib/voice/model-cache"
import type { WhisperModelSize } from "../lib/voice/model-constants"

const INITIAL_STATUS: ModelCacheStatus = {
  isCached: false,
  modelSize: null,
  modelName: null,
  cachedAt: null,
}

export function useModelCache() {
  const [modelStatus, setModelStatus] = useState<ModelCacheStatus>(INITIAL_STATUS)
  const [isDownloading, setIsDownloading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  // Check cache on mount
  const refreshStatus = useCallback(async () => {
    try {
      const info = await getCachedModelInfo()
      setModelStatus(info)
    } catch {
      // Cache API unavailable — leave as uncached
      setModelStatus(INITIAL_STATUS)
    }
  }, [])

  useEffect(() => {
    void refreshStatus()
  }, [refreshStatus])

  const download = useCallback(
    async (size: WhisperModelSize) => {
      setError(null)
      setIsDownloading(true)
      setProgress(0)

      try {
        await downloadModel(size, (percent) => {
          setProgress(percent)
        })
        await refreshStatus()
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Download failed"
        setError(message)
      } finally {
        setIsDownloading(false)
      }
    },
    [refreshStatus],
  )

  const remove = useCallback(
    async (size: WhisperModelSize) => {
      setError(null)

      try {
        await deleteModel(size)
        await refreshStatus()
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to delete model"
        setError(message)
      }
    },
    [refreshStatus],
  )

  return { modelStatus, isDownloading, progress, error, download, remove }
}
