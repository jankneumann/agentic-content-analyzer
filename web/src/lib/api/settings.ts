/**
 * Settings Management API Functions
 *
 * API client functions for model configuration, voice settings,
 * and connection status endpoints.
 */

import { apiClient } from "./client"
import type {
  ModelSettingsResponse,
  VoiceSettingsResponse,
  ConnectionStatusResponse,
} from "@/types/settings"

// ── Model Configuration ──

export async function fetchModelSettings(): Promise<ModelSettingsResponse> {
  return apiClient.get<ModelSettingsResponse>("/settings/models")
}

export async function updateModelForStep(
  step: string,
  modelId: string
): Promise<{ step: string; model_id: string; source: string }> {
  return apiClient.put(`/settings/models/${step}`, { model_id: modelId })
}

export async function resetModelForStep(
  step: string
): Promise<{ step: string; model_id: string; source: string }> {
  return apiClient.delete(`/settings/models/${step}`)
}

// ── Voice Configuration ──

export async function fetchVoiceSettings(): Promise<VoiceSettingsResponse> {
  return apiClient.get<VoiceSettingsResponse>("/settings/voice")
}

export async function updateVoiceSetting(
  field: string,
  value: string
): Promise<{ field: string; value: string; source: string }> {
  return apiClient.put(`/settings/voice/${field}`, { value })
}

export async function resetVoiceSetting(
  field: string
): Promise<{ field: string; value: string; source: string }> {
  return apiClient.delete(`/settings/voice/${field}`)
}

// ── Connection Status ──

export async function fetchConnectionStatus(): Promise<ConnectionStatusResponse> {
  return apiClient.get<ConnectionStatusResponse>("/status/connections")
}
