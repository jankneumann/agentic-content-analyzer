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
  presets: VoicePreset[]
  valid_providers: string[]
  valid_input_languages: string[]
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
