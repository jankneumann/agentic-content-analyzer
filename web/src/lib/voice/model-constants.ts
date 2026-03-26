export type WhisperModelSize = "tiny" | "base"

export interface WhisperModelInfo {
  size: WhisperModelSize
  name: string
  fileSize: number // bytes
  memoryEstimate: number // bytes during inference
  cdnUrl: string
  sha256: string // integrity check
}

export const WHISPER_MODELS: Record<WhisperModelSize, WhisperModelInfo> = {
  tiny: {
    size: "tiny",
    name: "ggml-tiny.en.bin",
    fileSize: 39_000_000, // ~39MB
    memoryEstimate: 200_000_000, // ~200MB
    cdnUrl: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin",
    sha256: "", // To be filled when pinning specific version
  },
  base: {
    size: "base",
    name: "ggml-base.en.bin",
    fileSize: 74_000_000, // ~74MB
    memoryEstimate: 500_000_000, // ~500MB
    cdnUrl: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin",
    sha256: "",
  },
}

export const MODEL_CACHE_NAME = "whisper-models-v1"
