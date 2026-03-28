/**
 * Floating Voice Input Overlay Panel
 *
 * Shows at the bottom-right of the window when voice input is activated
 * via the global shortcut or tray menu. Uses the existing useVoiceInput hook.
 *
 * Single-window DOM approach: no separate Tauri window, just a positioned div.
 * setAlwaysOnTop is toggled when the overlay appears/disappears.
 */

import { useCallback, useEffect, useState } from "react"
import { useGlobalShortcut } from "@/hooks/use-global-shortcut"
import { useVoiceInput } from "@/hooks/use-voice-input"
import { isTauri } from "@/lib/platform"

export function VoiceOverlay() {
  const [visible, setVisible] = useState(false)
  const { voiceToggleRequested, shortcutFailed, clearToggle } =
    useGlobalShortcut()
  const {
    isListening,
    transcript,
    interimTranscript,
    startListening,
    stopListening,
    resetTranscript,
  } = useVoiceInput({ continuous: true })

  // Handle tray menu actions
  useEffect(() => {
    if (!isTauri()) return

    const interval = setInterval(() => {
      const action = (window as any).__TAURI_TRAY_ACTION__
      if (action === "start_voice") {
        ;(window as any).__TAURI_TRAY_ACTION__ = null
        show()
      }
    }, 100)

    return () => clearInterval(interval)
  }, [])

  // Handle global shortcut toggle
  useEffect(() => {
    if (voiceToggleRequested) {
      clearToggle()
      if (visible) {
        hide()
      } else {
        show()
      }
    }
  }, [voiceToggleRequested])

  const show = useCallback(async () => {
    setVisible(true)
    resetTranscript()
    startListening()

    // Set window always-on-top while overlay is visible
    if (isTauri()) {
      try {
        const { getCurrentWebviewWindow } = await import(
          "@tauri-apps/api/webviewWindow"
        )
        const appWindow = getCurrentWebviewWindow()
        await appWindow.setAlwaysOnTop(true)
      } catch {
        // Non-critical — overlay still works without always-on-top
      }
    }
  }, [startListening, resetTranscript])

  const hide = useCallback(async () => {
    stopListening()
    setVisible(false)

    if (isTauri()) {
      try {
        const { getCurrentWebviewWindow } = await import(
          "@tauri-apps/api/webviewWindow"
        )
        const appWindow = getCurrentWebviewWindow()
        await appWindow.setAlwaysOnTop(false)
      } catch {
        // Non-critical
      }
    }
  }, [stopListening])

  // Handle Escape key to dismiss
  useEffect(() => {
    if (!visible) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        hide()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [visible, hide])

  // Show one-time notification if shortcut registration failed
  useEffect(() => {
    if (shortcutFailed) {
      import("sonner").then(({ toast }) => {
        toast.warning(
          "Global shortcut could not be registered. Voice input is still available via the UI button.",
          { duration: 8000 },
        )
      })
    }
  }, [shortcutFailed])

  if (!visible) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 rounded-xl border border-border bg-card p-4 shadow-2xl">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className={`h-3 w-3 rounded-full ${isListening ? "animate-pulse bg-red-500" : "bg-muted"}`}
          />
          <span className="text-sm font-medium text-foreground">
            {isListening ? "Listening..." : "Voice Input"}
          </span>
        </div>
        <button
          onClick={hide}
          className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Close voice overlay"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <div className="min-h-[60px] rounded-lg bg-muted/50 p-3 text-sm text-foreground">
        {transcript || interimTranscript ? (
          <>
            {transcript && <span>{transcript}</span>}
            {interimTranscript && (
              <span className="text-muted-foreground"> {interimTranscript}</span>
            )}
          </>
        ) : (
          <span className="text-muted-foreground">
            {isListening ? "Speak now..." : "Press shortcut to start"}
          </span>
        )}
      </div>

      <div className="mt-3 flex justify-end gap-2">
        <button
          onClick={() => {
            if (isListening) stopListening()
            else startListening()
          }}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
        >
          {isListening ? "Stop" : "Start"}
        </button>
        <button
          onClick={hide}
          className="rounded-md bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted/80"
        >
          Done
        </button>
      </div>
    </div>
  )
}
