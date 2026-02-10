/**
 * Prompt Management Types
 *
 * Types for the configurable LLM prompts feature.
 * Matches the backend API response models in settings_routes.py.
 */

/** Information about a prompt with override status */
export interface PromptInfo {
  key: string
  category: string
  name: string
  default_value: string
  current_value: string
  has_override: boolean
  version: number | null
  description: string | null
}

/** Response containing all prompts */
export interface PromptListResponse {
  prompts: PromptInfo[]
}

/** Request to update a prompt override */
export interface PromptUpdateRequest {
  value: string | null
  description?: string | null
}

/** Response after updating a prompt */
export interface PromptUpdateResponse {
  key: string
  current_value: string
  has_override: boolean
  version: number | null
}

/** Request to test a prompt template */
export interface PromptTestRequest {
  draft_value?: string | null
  variables?: Record<string, string>
}

/** Response from testing a prompt */
export interface PromptTestResponse {
  rendered_prompt: string
  variable_names: string[]
}
