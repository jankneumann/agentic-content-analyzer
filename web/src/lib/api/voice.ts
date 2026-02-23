/**
 * Voice API Functions
 *
 * API client functions for voice-related endpoints.
 */

import { apiClient } from "./client"

interface CleanupResponse {
  cleaned_text: string
}

/**
 * Clean up a raw voice transcript using an LLM.
 * Fixes grammar, removes filler words, and structures text.
 */
export async function cleanupTranscript(text: string): Promise<string> {
  const response = await apiClient.post<CleanupResponse>("/voice/cleanup", {
    text,
  })
  return response.cleaned_text
}
