/**
 * Settings Management Types
 *
 * Types for model configuration, voice settings, and connection status.
 * Matches the backend API response models.
 */

/** A single model option with cost data */
export interface ModelOption {
  id: string
  name: string
  family: string
  supports_vision: boolean
  supports_video: boolean
  supports_audio: boolean
  cost_per_mtok_input: number | null
  cost_per_mtok_output: number | null
  providers: string[]
}

/** Configuration for a single pipeline step */
export interface StepConfig {
  step: string
  current_model: string
  source: "env" | "db" | "default"
  env_var: string
  default_model: string
}

/** Full model settings response */
export interface ModelSettingsResponse {
  steps: StepConfig[]
  available_models: ModelOption[]
}

/** A voice setting with value and source */
export interface VoiceSettingInfo {
  key: string
  value: string
  source: "env" | "db" | "default"
}

/** A voice preset with provider-specific voices */
export interface VoicePreset {
  name: string
  voices: Record<string, string>
}

/** Full voice settings response */
export interface VoiceSettingsResponse {
  provider: VoiceSettingInfo
  default_voice: VoiceSettingInfo
  speed: VoiceSettingInfo
  input_language: VoiceSettingInfo
  input_continuous: VoiceSettingInfo
  input_auto_submit: VoiceSettingInfo
  cloud_stt_language: VoiceSettingInfo
  engine_preference_order: VoiceSettingInfo
  stt_model_size: VoiceSettingInfo
  cloud_stt_model: string
  presets: VoicePreset[]
  valid_providers: string[]
  valid_input_languages: string[]
  valid_cloud_stt_languages: string[]
  valid_engine_names: string[]
  valid_stt_model_sizes: string[]
}

// ── Ingestion Sources ──

/** Supported ingestion source types (matches the backend Source union) */
export type SourceType =
  | "blog"
  | "rss"
  | "substack"
  | "podcast"
  | "youtube_playlist"
  | "youtube_channel"
  | "youtube_rss"
  | "gmail"
  | "scholar"
  | "arxiv"
  | "huggingface_papers"
  | "websearch"

/** A single configured ingestion source */
export interface SourceInfo {
  type: string
  name: string | null
  url: string
  enabled: boolean
  tags: string[]
  origin: "yaml" | "db"
  source_key: string | null
}

/** Overview of all configured sources with content counts */
export interface SourcesOverview {
  sources: SourceInfo[]
  counts: Record<string, number>
  total_sources: number
  enabled_sources: number
}

/** Request body to add/update a source override */
export interface SourceUpsertRequest {
  config: Record<string, unknown>
  description?: string
}

/** Result of a source mutation (create / enable / disable) */
export interface SourceMutationResult {
  source_key: string
  version: number
  origin: string
  enabled: boolean
}

/** Result of a source deletion */
export interface SourceDeleteResult {
  source_key: string
  deleted: boolean
}

/** Health status for a single service */
export interface ServiceStatus {
  name: string
  status: "ok" | "unavailable" | "not_configured" | "error"
  details: string
  latency_ms: number | null
}

/** Connection status response */
export interface ConnectionStatusResponse {
  services: ServiceStatus[]
  all_ok: boolean
}
