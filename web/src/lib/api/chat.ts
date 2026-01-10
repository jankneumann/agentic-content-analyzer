/**
 * Chat API Functions
 *
 * API functions for the AI revision chatbot.
 * Supports conversation management and SSE streaming for real-time responses.
 *
 * @example
 * // Create a conversation
 * const conversation = await createConversation({
 *   artifactType: 'summary',
 *   artifactId: '123',
 * })
 *
 * @example
 * // Send a message with streaming
 * await sendMessage(conversationId, { content: 'Make this more concise' }, (chunk) => {
 *   console.log(chunk.content)
 * })
 */

import { apiClient } from "./client"
import type {
  Conversation,
  ConversationListItem,
  CreateConversationRequest,
  SendMessageRequest,
  MessageChunk,
  ChatMessage,
  ChatConfig,
  ArtifactType,
  PaginatedResponse,
} from "@/types"

/** Raw API response type (snake_case) */
interface ChatConfigApiResponse {
  available_models: { id: string; name: string; provider: string }[]
  default_model: string
  web_search_enabled: boolean
  max_message_length: number
  max_history_length: number
}

/**
 * Fetch chat configuration
 *
 * Returns available models, limits, and feature flags.
 *
 * @returns Chat configuration
 */
export async function fetchChatConfig(): Promise<ChatConfig> {
  const response = await apiClient.get<ChatConfigApiResponse>("/chat/config")

  // Transform snake_case to camelCase
  return {
    availableModels: response.available_models,
    defaultModel: response.default_model,
    webSearchEnabled: response.web_search_enabled,
    maxMessageLength: response.max_message_length,
    maxHistoryLength: response.max_history_length,
  }
}

/**
 * Filters for listing conversations
 */
export interface ConversationFilters {
  /** Filter by artifact type */
  artifactType?: ArtifactType
  /** Filter by artifact ID */
  artifactId?: string
  /** Pagination offset */
  offset?: number
  /** Pagination limit */
  limit?: number
}

/**
 * Fetch paginated list of conversations
 *
 * @param filters - Optional filters
 * @returns Paginated list of conversations
 */
export async function fetchConversations(
  filters?: ConversationFilters
): Promise<PaginatedResponse<ConversationListItem>> {
  return apiClient.get<PaginatedResponse<ConversationListItem>>("/chat/conversations", {
    params: filters as Record<string, string | number | boolean | undefined>,
  })
}

/**
 * Fetch a single conversation by ID
 *
 * @param conversationId - Conversation ID
 * @returns Full conversation with messages
 */
export async function fetchConversation(conversationId: string): Promise<Conversation> {
  return apiClient.get<Conversation>(`/chat/conversations/${conversationId}`)
}

/**
 * Fetch conversations for a specific artifact
 *
 * @param artifactType - Type of artifact (summary, digest, script)
 * @param artifactId - ID of the artifact
 * @returns List of conversations for this artifact
 */
export async function fetchConversationsForArtifact(
  artifactType: ArtifactType,
  artifactId: string
): Promise<ConversationListItem[]> {
  const result = await apiClient.get<PaginatedResponse<ConversationListItem>>(
    "/chat/conversations",
    {
      params: {
        artifact_type: artifactType,
        artifact_id: artifactId,
        limit: 50,
      },
    }
  )
  return result.items
}

/**
 * Create a new conversation
 *
 * @param request - Conversation creation request
 * @returns Created conversation
 */
export async function createConversation(
  request: CreateConversationRequest
): Promise<Conversation> {
  return apiClient.post<Conversation>("/chat/conversations", {
    artifact_type: request.artifactType,
    artifact_id: request.artifactId,
    initial_message: request.initialMessage,
    title: request.title,
  })
}

/**
 * Delete a conversation
 *
 * @param conversationId - Conversation ID to delete
 */
export async function deleteConversation(conversationId: string): Promise<void> {
  return apiClient.delete(`/chat/conversations/${conversationId}`)
}

/**
 * Send a message to a conversation with SSE streaming
 *
 * Uses Server-Sent Events for real-time streaming of assistant responses.
 *
 * @param conversationId - Conversation to send to
 * @param request - Message content and options
 * @param onChunk - Callback for each streaming chunk
 * @returns Complete assistant message once finished
 */
export async function sendMessage(
  conversationId: string,
  request: SendMessageRequest,
  onChunk?: (chunk: MessageChunk) => void
): Promise<ChatMessage> {
  return new Promise((resolve, reject) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ""

    // Convert request to API format
    const body = {
      content: request.content,
      enable_web_search: request.enableWebSearch ?? false,
      model: request.model,
    }

    fetch(`${baseUrl}/api/v1/chat/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error("No response body")
        }

        const decoder = new TextDecoder()
        let buffer = ""
        let messageId = ""
        let fullContent = ""
        let metadata: MessageChunk["metadata"]

        const processStream = async () => {
          while (true) {
            const { done, value } = await reader.read()

            if (done) break

            buffer += decoder.decode(value, { stream: true })

            // Process complete SSE messages
            const lines = buffer.split("\n")
            buffer = lines.pop() || "" // Keep incomplete line in buffer

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const chunk = JSON.parse(line.slice(6)) as MessageChunk
                  onChunk?.(chunk)

                  switch (chunk.type) {
                    case "start":
                      messageId = chunk.messageId || ""
                      fullContent = ""
                      break

                    case "delta":
                      fullContent += chunk.content || ""
                      break

                    case "end":
                      metadata = chunk.metadata
                      // Stream complete - resolve with full message
                      resolve({
                        id: messageId,
                        role: "assistant",
                        content: fullContent,
                        timestamp: new Date().toISOString(),
                        metadata,
                      })
                      return

                    case "error":
                      reject(new Error(chunk.error || "Message generation failed"))
                      return
                  }
                } catch {
                  // Skip malformed JSON
                }
              }
            }
          }

          // Stream ended without explicit completion
          if (fullContent) {
            resolve({
              id: messageId || crypto.randomUUID(),
              role: "assistant",
              content: fullContent,
              timestamp: new Date().toISOString(),
              metadata,
            })
          } else {
            reject(new Error("Stream ended without response"))
          }
        }

        processStream().catch(reject)
      })
      .catch(reject)
  })
}

/**
 * Regenerate the last assistant message
 *
 * @param conversationId - Conversation ID
 * @param onChunk - Callback for streaming chunks
 * @returns Regenerated message
 */
export async function regenerateLastMessage(
  conversationId: string,
  onChunk?: (chunk: MessageChunk) => void
): Promise<ChatMessage> {
  return new Promise((resolve, reject) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ""

    fetch(`${baseUrl}/api/v1/chat/conversations/${conversationId}/regenerate`, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error("No response body")
        }

        const decoder = new TextDecoder()
        let buffer = ""
        let messageId = ""
        let fullContent = ""
        let metadata: MessageChunk["metadata"]

        const processStream = async () => {
          while (true) {
            const { done, value } = await reader.read()

            if (done) break

            buffer += decoder.decode(value, { stream: true })

            const lines = buffer.split("\n")
            buffer = lines.pop() || ""

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const chunk = JSON.parse(line.slice(6)) as MessageChunk
                  onChunk?.(chunk)

                  switch (chunk.type) {
                    case "start":
                      messageId = chunk.messageId || ""
                      fullContent = ""
                      break

                    case "delta":
                      fullContent += chunk.content || ""
                      break

                    case "end":
                      metadata = chunk.metadata
                      resolve({
                        id: messageId,
                        role: "assistant",
                        content: fullContent,
                        timestamp: new Date().toISOString(),
                        metadata,
                      })
                      return

                    case "error":
                      reject(new Error(chunk.error || "Regeneration failed"))
                      return
                  }
                } catch {
                  // Skip malformed JSON
                }
              }
            }
          }

          if (fullContent) {
            resolve({
              id: messageId || crypto.randomUUID(),
              role: "assistant",
              content: fullContent,
              timestamp: new Date().toISOString(),
              metadata,
            })
          } else {
            reject(new Error("Stream ended without response"))
          }
        }

        processStream().catch(reject)
      })
      .catch(reject)
  })
}

/**
 * Apply a suggested action from the chat
 *
 * Applies changes suggested by the assistant to the artifact.
 *
 * @param conversationId - Conversation ID
 * @param messageId - Message containing the suggestion
 * @param actionIndex - Index of the action to apply (if multiple)
 * @returns Updated artifact data
 */
export async function applySuggestedAction<T = unknown>(
  conversationId: string,
  messageId: string,
  actionIndex: number = 0
): Promise<T> {
  return apiClient.post<T>(`/chat/conversations/${conversationId}/apply-action`, {
    message_id: messageId,
    action_index: actionIndex,
  })
}

/**
 * Get message history for a conversation
 *
 * @param conversationId - Conversation ID
 * @param limit - Maximum number of messages to return
 * @param before - Return messages before this message ID
 * @returns Array of messages
 */
export async function fetchMessages(
  conversationId: string,
  limit?: number,
  before?: string
): Promise<ChatMessage[]> {
  return apiClient.get<ChatMessage[]>(`/chat/conversations/${conversationId}/messages`, {
    params: { limit, before },
  })
}
