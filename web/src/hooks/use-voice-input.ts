/**
 * useVoiceInput Hook
 *
 * Wraps the Web Speech API (SpeechRecognition) for voice-to-text input.
 * Provides feature detection, interim/final transcript state, error handling,
 * and configurable language/continuous mode.
 */

import { useState, useCallback, useRef, useEffect } from "react"

// Web Speech API types (not yet in all TS libs)
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList
  resultIndex: number
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string
  message: string
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

/** User-facing error messages keyed by SpeechRecognition error codes */
const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed":
    "Microphone access was denied. Please allow microphone access in your browser settings.",
  "no-speech": "No speech was detected. Please try again.",
  network: "A network error occurred. Voice input requires an internet connection.",
  "audio-capture":
    "No microphone was found. Please connect a microphone and try again.",
  "service-not-allowed":
    "Speech recognition service is not allowed. Please check your browser settings.",
  aborted: "Voice input was cancelled.",
  "language-not-supported":
    "The selected language is not supported for voice input.",
}

export interface UseVoiceInputOptions {
  /** BCP-47 language tag (e.g., "en-US") */
  lang?: string
  /** Whether to keep listening after pauses */
  continuous?: boolean
  /** Callback when a final transcript is received */
  onResult?: (transcript: string) => void
  /** Callback when an error occurs */
  onError?: (error: string) => void
}

export interface UseVoiceInputReturn {
  /** Whether the Web Speech API is available in this browser */
  isSupported: boolean
  /** Whether voice input is currently active */
  isListening: boolean
  /** Whether on-device transcription is processing (after recording stops) */
  isProcessing: boolean
  /** In-progress (interim) transcript text */
  interimTranscript: string
  /** Final committed transcript text */
  transcript: string
  /** Current error message, if any */
  error: string | null
  /** Start listening for voice input */
  startListening: () => void
  /** Stop listening for voice input */
  stopListening: () => void
  /** Toggle listening on/off */
  toggleListening: () => void
  /** Clear all transcript state */
  resetTranscript: () => void
}

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

export function useVoiceInput(
  options: UseVoiceInputOptions = {}
): UseVoiceInputReturn {
  const { lang = "en-US", continuous = false, onResult, onError } = options

  const isSupported = getSpeechRecognition() !== null
  const [isListening, setIsListening] = useState(false)
  const [interimTranscript, setInterimTranscript] = useState("")
  const [transcript, setTranscript] = useState("")
  const [error, setError] = useState<string | null>(null)

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)
  const onResultRef = useRef(onResult)
  const onErrorRef = useRef(onError)

  // Keep callback refs fresh without re-creating recognition instance
  useEffect(() => {
    onResultRef.current = onResult
  }, [onResult])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort()
        recognitionRef.current = null
      }
    }
  }, [])

  const startListening = useCallback(() => {
    const SpeechRecognition = getSpeechRecognition()
    if (!SpeechRecognition) return

    // Stop any existing instance
    if (recognitionRef.current) {
      recognitionRef.current.abort()
    }

    setError(null)
    setInterimTranscript("")

    const recognition = new SpeechRecognition()
    recognition.continuous = continuous
    recognition.interimResults = true
    recognition.lang = lang

    recognition.onstart = () => {
      setIsListening(true)
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = ""
      let final = ""

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          final += result[0].transcript
        } else {
          interim += result[0].transcript
        }
      }

      setInterimTranscript(interim)

      if (final) {
        setTranscript((prev) => {
          const updated = prev ? `${prev} ${final}` : final
          onResultRef.current?.(final)
          return updated
        })
      }
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const message =
        ERROR_MESSAGES[event.error] ??
        `Voice input error: ${event.error}`
      setError(message)
      setIsListening(false)
      onErrorRef.current?.(message)
    }

    recognition.onend = () => {
      setIsListening(false)
      setInterimTranscript("")
    }

    recognitionRef.current = recognition

    try {
      recognition.start()
    } catch {
      setError("Failed to start voice input. Please try again.")
      setIsListening(false)
    }
  }, [lang, continuous])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
    }
  }, [])

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening()
    } else {
      startListening()
    }
  }, [isListening, startListening, stopListening])

  const resetTranscript = useCallback(() => {
    setTranscript("")
    setInterimTranscript("")
    setError(null)
  }, [])

  return {
    isSupported,
    isListening,
    isProcessing: false, // TODO: Wire to STTEngine state when hook is refactored (T1.5)
    interimTranscript,
    transcript,
    error,
    startListening,
    stopListening,
    toggleListening,
    resetTranscript,
  }
}
