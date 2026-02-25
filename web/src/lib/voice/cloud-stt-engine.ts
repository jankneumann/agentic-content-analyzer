/**
 * Cloud STT Engine
 *
 * Implements the STTEngine interface using a WebSocket connection to the
 * backend, which proxies audio to a cloud STT provider (Gemini, Whisper,
 * or Deepgram) and streams transcript results back.
 *
 * Features:
 * - MediaRecorder-based audio capture with AudioContext PCM conversion
 * - WebSocket binary streaming at 100-250ms intervals
 * - Automatic reconnection with exponential backoff (1s, 2s, 4s, max 3 retries)
 * - Propagates `cleaned` flag from provider (Gemini returns cleaned=true)
 */

import type { STTEngine, STTEngineEvents, STTEngineState, STTStartOptions } from "./engine"

/** WebSocket message from the server */
interface ServerMessage {
  type: "interim" | "final" | "error"
  text: string
  cleaned: boolean
  confidence?: number
}

/** Configuration for the cloud STT engine */
export interface CloudSTTConfig {
  /** Base URL for the WebSocket endpoint (defaults to current origin) */
  baseUrl?: string
  /** Admin API key for authentication */
  apiKey?: string
}

const MAX_RECONNECT_RETRIES = 3
const INITIAL_RECONNECT_DELAY = 1000 // 1 second

export class CloudSTTEngine implements STTEngine {
  readonly id = "cloud" as const
  readonly name = "Cloud STT"

  private config: CloudSTTConfig
  private ws: WebSocket | null = null
  private mediaRecorder: MediaRecorder | null = null
  private audioContext: AudioContext | null = null
  private events: STTEngineEvents | null = null
  private state: STTEngineState = "idle"
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private language = "auto"
  // private continuous = false

  constructor(config: CloudSTTConfig = {}) {
    this.config = config
  }

  isAvailable(): boolean {
    // Cloud STT requires MediaRecorder and WebSocket support
    return (
      typeof window !== "undefined" &&
      typeof WebSocket !== "undefined" &&
      typeof MediaRecorder !== "undefined" &&
      typeof AudioContext !== "undefined"
    )
  }

  start(options: STTStartOptions): void {
    this.events = options.events
    this.language = options.language ?? "auto"
    // this.continuous = options.continuous ?? false
    this.reconnectAttempts = 0
    this.connect()
  }

  stop(): void {
    this.stopRecording()
    this.closeWebSocket()
    this.setState("idle")
  }

  destroy(): void {
    this.stop()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.audioContext) {
      this.audioContext.close()
      this.audioContext = null
    }
  }

  private setState(state: STTEngineState): void {
    this.state = state
    this.events?.onStateChange(state)
  }

  private connect(): void {
    this.setState("starting")

    const baseUrl = this.config.baseUrl ?? window.location.origin
    const wsProtocol = baseUrl.startsWith("https") ? "wss" : "ws"
    const wsBase = baseUrl.replace(/^https?/, wsProtocol)

    const params = new URLSearchParams()
    if (this.config.apiKey) {
      params.set("X-Admin-Key", this.config.apiKey)
    }
    params.set("language", this.language)

    const url = `${wsBase}/ws/voice/stream?${params.toString()}`

    try {
      this.ws = new WebSocket(url)
      this.ws.binaryType = "arraybuffer"

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.setState("listening")
        this.startRecording()
      }

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const msg: ServerMessage = JSON.parse(event.data as string)
          if (msg.type === "error") {
            this.events?.onError(msg.text)
          } else {
            this.events?.onResult({
              text: msg.text,
              isFinal: msg.type === "final",
              cleaned: msg.cleaned,
              confidence: msg.confidence,
            })
          }
        } catch {
          // Ignore parse errors
        }
      }

      this.ws.onclose = (event) => {
        if (event.code === 4001) {
          this.events?.onError("Authentication failed for cloud STT")
          this.setState("error")
          return
        }

        if (this.state === "listening" || this.state === "reconnecting") {
          this.attemptReconnect()
        }
      }

      this.ws.onerror = () => {
        // onclose will fire after onerror — reconnection handled there
      }
    } catch (e) {
      this.events?.onError(`Failed to connect: ${e}`)
      this.setState("error")
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_RETRIES) {
      this.events?.onError("Failed to reconnect after multiple attempts")
      this.setState("error")
      return
    }

    this.setState("reconnecting")
    const delay = INITIAL_RECONNECT_DELAY * Math.pow(2, this.reconnectAttempts)
    this.reconnectAttempts++

    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }

  private async startRecording(): Promise<void> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })

      // Use AudioContext to get PCM data
      this.audioContext = new AudioContext({ sampleRate: 16000 })
      const source = this.audioContext.createMediaStreamSource(stream)
      const processor = this.audioContext.createScriptProcessor(4096, 1, 1)

      processor.onaudioprocess = (e: AudioProcessingEvent) => {
        if (this.ws?.readyState !== WebSocket.OPEN) return

        const inputData = e.inputBuffer.getChannelData(0)
        // Convert Float32 to Int16 PCM
        const pcmData = new Int16Array(inputData.length)
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]))
          pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff
        }
        this.ws.send(pcmData.buffer)
      }

      source.connect(processor)
      processor.connect(this.audioContext.destination)

      // Store stream for cleanup
      this.mediaRecorder = { stream } as unknown as MediaRecorder
    } catch (e) {
      this.events?.onError(
        `Microphone access denied or unavailable: ${e}`
      )
      this.setState("error")
    }
  }

  private stopRecording(): void {
    if (this.mediaRecorder) {
      const stream = (this.mediaRecorder as unknown as { stream: MediaStream }).stream
      stream?.getTracks().forEach((track) => track.stop())
      this.mediaRecorder = null
    }
  }

  private closeWebSocket(): void {
    if (this.ws) {
      this.ws.onclose = null
      this.ws.onerror = null
      this.ws.onmessage = null
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.close()
      }
      this.ws = null
    }
  }
}
