/**
 * Browser STT Engine
 *
 * Wraps the Web Speech API (SpeechRecognition) to implement the STTEngine
 * interface. Returns raw transcripts (cleaned=false).
 */

import type { STTEngine, STTEngineState, STTStartOptions } from "./engine"

// Web Speech API types
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList
  resultIndex: number
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string
}

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean
  interimResults: boolean
  lang: string
  start(): void
  stop(): void
  abort(): void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance

function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null
  return (
    (window as unknown as Record<string, SpeechRecognitionConstructor>)
      .SpeechRecognition ??
    (window as unknown as Record<string, SpeechRecognitionConstructor>)
      .webkitSpeechRecognition ??
    null
  )
}

const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed": "Microphone access was denied.",
  "no-speech": "No speech was detected.",
  network: "A network error occurred.",
  "audio-capture": "No microphone was found.",
  aborted: "Voice input was cancelled.",
}

export class BrowserSTTEngine implements STTEngine {
  readonly id = "browser" as const
  readonly name = "Browser (Web Speech API)"

  private recognition: SpeechRecognitionInstance | null = null

  isAvailable(): boolean {
    return getSpeechRecognition() !== null
  }

  start(options: STTStartOptions): void {
    const SR = getSpeechRecognition()
    if (!SR) {
      options.events.onError("Web Speech API not supported in this browser")
      return
    }

    if (this.recognition) {
      this.recognition.abort()
    }

    const recognition = new SR()
    recognition.continuous = options.continuous ?? false
    recognition.interimResults = true
    recognition.lang = options.language ?? "en-US"

    recognition.onstart = () => {
      options.events.onStateChange("listening")
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        options.events.onResult({
          text: result[0].transcript,
          isFinal: result.isFinal,
          cleaned: false, // Browser STT returns raw transcripts
          confidence: result[0].confidence,
        })
      }
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const message = ERROR_MESSAGES[event.error] ?? `Voice input error: ${event.error}`
      options.events.onError(message)
      options.events.onStateChange("error")
    }

    recognition.onend = () => {
      options.events.onStateChange("idle")
    }

    this.recognition = recognition

    try {
      recognition.start()
    } catch {
      options.events.onError("Failed to start voice input")
      options.events.onStateChange("error")
    }
  }

  stop(): void {
    this.recognition?.stop()
  }

  destroy(): void {
    this.recognition?.abort()
    this.recognition = null
  }
}
