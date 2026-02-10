/**
 * Prompt Management API Functions
 *
 * API client functions for the prompt management endpoints.
 * All endpoints require admin authentication (X-Admin-Key header).
 */

import { apiClient } from "./client"
import type {
  PromptListResponse,
  PromptInfo,
  PromptUpdateRequest,
  PromptUpdateResponse,
  PromptTestRequest,
  PromptTestResponse,
} from "@/types/prompt"

/**
 * Fetch all prompts with override status
 */
export async function fetchPrompts(): Promise<PromptListResponse> {
  return apiClient.get<PromptListResponse>("/settings/prompts")
}

/**
 * Fetch a single prompt by key
 */
export async function fetchPrompt(key: string): Promise<PromptInfo> {
  return apiClient.get<PromptInfo>(`/settings/prompts/${key}`)
}

/**
 * Update a prompt override
 */
export async function updatePrompt(
  key: string,
  data: PromptUpdateRequest
): Promise<PromptUpdateResponse> {
  return apiClient.put<PromptUpdateResponse>(`/settings/prompts/${key}`, data)
}

/**
 * Reset a prompt override to default
 */
export async function resetPrompt(key: string): Promise<PromptUpdateResponse> {
  return apiClient.delete<PromptUpdateResponse>(`/settings/prompts/${key}`)
}

/**
 * Test a prompt template by rendering it
 */
export async function testPrompt(
  key: string,
  data: PromptTestRequest
): Promise<PromptTestResponse> {
  return apiClient.post<PromptTestResponse>(
    `/settings/prompts/${key}/test`,
    data
  )
}
