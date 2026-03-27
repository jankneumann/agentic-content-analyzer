/**
 * Native STT Engine
 *
 * Wraps @capacitor-community/speech-recognition to implement the STTEngine
 * interface. Only available on native Capacitor platforms (iOS/Android).
 * Uses lazy initialization to avoid importing the Capacitor plugin until needed.
 */

import type { STTEngine, STTEngineState, STTStartOptions } from "./engine"

/** Minimal type for the SpeechRecognition Capacitor plugin */
interface SpeechRecognitionPlugin {
  available(): Promise<{ available: boolean }>
  requestPermissions(): Promise<{ speechRecognition: string }>
  checkPermissions(): Promise<{ speechRecognition: string }>
  start(options: {
    language?: string
    maxResults?: number
    partialResults?: boolean
    popup?: boolean
  }): Promise<void>
  stop(): Promise<void>
  addListener(
    event: "partialResults",
    callback: (data: { matches: string[] }) => void
  ): Promise<{ remove: () => void }>
  removeAllListeners(): Promise<void>
}

export class NativeSTTEngine implements STTEngine {
  readonly id = "native" as const
  readonly name = "Native Speech Recognition"

  private plugin: SpeechRecognitionPlugin | null = null
  private state: STTEngineState = "idle"
  private listenerHandle: { remove: () => void } | null = null

  async isAvailable(): Promise<boolean> {
    try {
      const { Capacitor } = await import("@capacitor/core")
      if (!Capacitor.isNativePlatform()) return false

      const mod = await import("@capacitor-community/speech-recognition")
      const speechPlugin = mod.SpeechRecognition as unknown as SpeechRecognitionPlugin
      this.plugin = speechPlugin

      const { available } = await speechPlugin.available()
      return available
    } catch {
      return false
    }
  }

  start(options: STTStartOptions): void {
    void this.startAsync(options)
  }

  private async startAsync(options: STTStartOptions): Promise<void> {
    options.events.onStateChange("starting")
    this.state = "starting"

    try {
      // Lazy-load plugin if not yet loaded
      if (!this.plugin) {
        const mod = await import("@capacitor-community/speech-recognition")
        this.plugin = mod.SpeechRecognition as unknown as SpeechRecognitionPlugin
      }

      // Request permissions on first use
      const permResult = await this.plugin.checkPermissions()
      if (permResult.speechRecognition !== "granted") {
        const reqResult = await this.plugin.requestPermissions()
        if (reqResult.speechRecognition !== "granted") {
          options.events.onError("Speech recognition permission was denied.")
          options.events.onStateChange("error")
          this.state = "error"
          return
        }
      }

      // Listen for partial results
      this.listenerHandle = await this.plugin.addListener(
        "partialResults",
        (data: { matches: string[] }) => {
          if (data.matches && data.matches.length > 0) {
            options.events.onResult({
              text: data.matches[0],
              isFinal: false,
              cleaned: false,
              confidence: undefined,
            })
          }
        }
      )

      // Start recognition
      const language = options.language && options.language !== "auto"
        ? options.language
        : "en-US"

      await this.plugin.start({
        language,
        partialResults: true,
        popup: false,
      })

      this.state = "listening"
      options.events.onStateChange("listening")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start native speech recognition"
      options.events.onError(message)
      options.events.onStateChange("error")
      this.state = "error"
    }
  }

  stop(): void {
    if (!this.plugin || this.state === "idle") return
    void this.stopAsync()
  }

  private async stopAsync(): Promise<void> {
    try {
      await this.plugin?.stop()
    } catch {
      // Ignore stop errors
    }
    this.state = "idle"
  }

  destroy(): void {
    void this.destroyAsync()
  }

  private async destroyAsync(): Promise<void> {
    try {
      await this.plugin?.stop()
    } catch {
      // Ignore errors during cleanup
    }
    try {
      if (this.listenerHandle) {
        this.listenerHandle.remove()
        this.listenerHandle = null
      }
      await this.plugin?.removeAllListeners()
    } catch {
      // Ignore errors during cleanup
    }
    this.plugin = null
    this.state = "idle"
  }
}
