export interface AudioRecorderOptions {
  sampleRate?: number // default: 16000
  channelCount?: number // default: 1 (mono)
}

const DEFAULT_SAMPLE_RATE = 16000
const DEFAULT_CHANNEL_COUNT = 1
const PREFERRED_MIME_TYPE = "audio/webm;codecs=opus"

export class AudioRecorder {
  private stream: MediaStream | null = null
  private mediaRecorder: MediaRecorder | null = null
  private chunks: Blob[] = []
  private _isRecording = false

  /**
   * Request microphone permission and store the stream for later use.
   * Returns true on success, false on denial. Never throws.
   */
  async requestPermission(): Promise<boolean> {
    try {
      if (
        typeof navigator === "undefined" ||
        !navigator.mediaDevices?.getUserMedia
      ) {
        console.error(
          "[AudioRecorder] getUserMedia is not available in this environment"
        )
        return false
      }

      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      return true
    } catch (error) {
      console.error("[AudioRecorder] Microphone permission denied:", error)
      return false
    }
  }

  /**
   * Start recording audio from the microphone.
   * Requests permission if not already granted.
   */
  async startRecording(options?: AudioRecorderOptions): Promise<void> {
    if (this._isRecording) {
      return
    }

    // Request permission if we don't have a stream yet
    if (!this.stream) {
      const granted = await this.requestPermission()
      if (!granted) {
        throw new Error("Microphone permission not granted")
      }
    }

    this.chunks = []

    const mimeType = MediaRecorder.isTypeSupported(PREFERRED_MIME_TYPE)
      ? PREFERRED_MIME_TYPE
      : undefined

    const recorderOptions: MediaRecorderOptions = {}
    if (mimeType) {
      recorderOptions.mimeType = mimeType
    }

    this.mediaRecorder = new MediaRecorder(this.stream!, recorderOptions)

    this.mediaRecorder.ondataavailable = (event: BlobEvent) => {
      if (event.data.size > 0) {
        this.chunks.push(event.data)
      }
    }

    this.mediaRecorder.start()
    this._isRecording = true

    // Store options for use during stop/conversion (capture in closure via class)
    this._options = {
      sampleRate: options?.sampleRate ?? DEFAULT_SAMPLE_RATE,
      channelCount: options?.channelCount ?? DEFAULT_CHANNEL_COUNT,
    }
  }

  private _options: Required<AudioRecorderOptions> = {
    sampleRate: DEFAULT_SAMPLE_RATE,
    channelCount: DEFAULT_CHANNEL_COUNT,
  }

  /**
   * Stop recording and return the captured audio as a Float32Array
   * resampled to 16kHz mono PCM (the format Whisper expects).
   */
  async stopRecording(): Promise<Float32Array> {
    if (!this.mediaRecorder || !this._isRecording) {
      throw new Error("Not currently recording")
    }

    const audioData = await new Promise<Blob>((resolve, reject) => {
      const recorder = this.mediaRecorder!

      recorder.onstop = () => {
        const blob = new Blob(this.chunks, {
          type: recorder.mimeType || "audio/webm",
        })
        resolve(blob)
      }

      recorder.onerror = (event) => {
        reject(
          new Error(
            `MediaRecorder error: ${(event as ErrorEvent).message || "unknown"}`
          )
        )
      }

      recorder.stop()
    })

    this._isRecording = false

    // Convert the blob to Float32Array via AudioContext resampling
    const arrayBuffer = await audioData.arrayBuffer()
    const audioContext = new AudioContext({
      sampleRate: this._options.sampleRate,
    })

    try {
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
      // Get mono channel data (channel 0) as Float32Array
      return audioBuffer.getChannelData(0)
    } finally {
      await audioContext.close()
    }
  }

  /**
   * Whether the recorder is currently capturing audio.
   */
  isRecording(): boolean {
    return this._isRecording
  }

  /**
   * Release all resources: stop tracks, release the MediaStream,
   * and null out references.
   */
  destroy(): void {
    if (this._isRecording && this.mediaRecorder) {
      try {
        this.mediaRecorder.stop()
      } catch {
        // Ignore errors during cleanup
      }
      this._isRecording = false
    }

    if (this.stream) {
      for (const track of this.stream.getTracks()) {
        track.stop()
      }
    }

    this.stream = null
    this.mediaRecorder = null
    this.chunks = []
  }
}
