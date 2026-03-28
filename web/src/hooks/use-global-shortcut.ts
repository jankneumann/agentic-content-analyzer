/**
 * Bridge between Tauri global shortcut events and React state.
 *
 * Listens for window.__TAURI_VOICE_TOGGLE__ changes (set by Rust shortcut handler)
 * and triggers the voice overlay.
 */

import { useEffect, useRef, useState } from "react"
import { isTauri } from "@/lib/platform"

interface UseGlobalShortcutResult {
  voiceToggleRequested: boolean
  shortcutFailed: boolean
  clearToggle: () => void
}

export function useGlobalShortcut(): UseGlobalShortcutResult {
  const [voiceToggleRequested, setVoiceToggleRequested] = useState(false)
  const [shortcutFailed, setShortcutFailed] = useState(false)
  const lastToggle = useRef(0)

  useEffect(() => {
    if (!isTauri()) return

    // Check for shortcut registration failure
    if ((window as any).__TAURI_SHORTCUT_FAILED__) {
      setShortcutFailed(true)
    }

    // Poll for voice toggle events from Rust
    const interval = setInterval(() => {
      const timestamp = (window as any).__TAURI_VOICE_TOGGLE__
      if (timestamp && timestamp !== lastToggle.current) {
        lastToggle.current = timestamp
        setVoiceToggleRequested(true)
      }
    }, 100)

    return () => clearInterval(interval)
  }, [])

  const clearToggle = () => setVoiceToggleRequested(false)

  return { voiceToggleRequested, shortcutFailed, clearToggle }
}
