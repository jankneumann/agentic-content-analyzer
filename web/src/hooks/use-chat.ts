/**
 * Chat React Query Hooks
 *
 * Custom hooks for the AI revision chatbot.
 * Provides conversation management and real-time message streaming.
 *
 * @example
 * // Load conversations for an artifact
 * const { data } = useConversationsForArtifact('summary', '123')
 *
 * @example
 * // Send a message with streaming
 * const { sendMessage, isStreaming, streamingContent } = useSendMessage()
 * sendMessage({ conversationId, content: 'Make this more concise' })
 */

import { useState, useCallback, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/api/query-keys"
import {
  fetchChatConfig,
  fetchConversations,
  fetchConversation,
  fetchConversationsForArtifact,
  createConversation,
  deleteConversation,
  sendMessage as sendMessageApi,
  regenerateLastMessage,
  applySuggestedAction,
  type ConversationFilters,
} from "@/lib/api/chat"
import type {
  ArtifactType,
  Conversation,
  ChatMessage,
  MessageChunk,
} from "@/types"

/**
 * Hook to fetch chat configuration
 *
 * Returns available models, limits, and feature flags.
 */
export function useChatConfig() {
  return useQuery({
    queryKey: queryKeys.chat.config(),
    queryFn: fetchChatConfig,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to fetch paginated list of conversations
 *
 * @param filters - Optional filters
 * @returns Query result with conversations
 */
export function useConversations(filters?: ConversationFilters) {
  return useQuery({
    queryKey: queryKeys.chat.conversationList(filters?.artifactType, filters?.artifactId),
    queryFn: () => fetchConversations(filters),
  })
}

/**
 * Hook to fetch a single conversation with messages
 *
 * @param conversationId - Conversation ID
 * @param options - Query options
 * @returns Query result with conversation
 */
export function useConversation(conversationId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.chat.conversation(conversationId),
    queryFn: () => fetchConversation(conversationId),
    enabled: options?.enabled ?? !!conversationId,
  })
}

/**
 * Hook to fetch conversations for a specific artifact
 *
 * Useful for showing conversation history in the review UI.
 *
 * @param artifactType - Type of artifact (summary, digest, script)
 * @param artifactId - ID of the artifact
 * @param options - Query options
 */
export function useConversationsForArtifact(
  artifactType: ArtifactType,
  artifactId: string,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.chat.conversationList(artifactType, artifactId),
    queryFn: () => fetchConversationsForArtifact(artifactType, artifactId),
    enabled: options?.enabled ?? !!(artifactType && artifactId),
  })
}

/**
 * Hook to create a new conversation
 *
 * @example
 * const { mutate: startConversation } = useCreateConversation()
 * startConversation({
 *   artifactType: 'summary',
 *   artifactId: '123',
 *   initialMessage: 'Help me improve this summary'
 * })
 */
export function useCreateConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createConversation,
    onSuccess: (conversation) => {
      // Add to cache
      queryClient.setQueryData(
        queryKeys.chat.conversation(conversation.id),
        conversation
      )
      // Invalidate conversation lists
      queryClient.invalidateQueries({
        queryKey: queryKeys.chat.conversations(),
      })
    },
  })
}

/**
 * Hook to delete a conversation
 */
export function useDeleteConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteConversation,
    onSuccess: (_data, conversationId) => {
      // Remove from cache
      queryClient.removeQueries({
        queryKey: queryKeys.chat.conversation(conversationId),
      })
      // Invalidate lists
      queryClient.invalidateQueries({
        queryKey: queryKeys.chat.conversations(),
      })
    },
  })
}

/**
 * State returned by useSendMessage hook
 */
interface SendMessageState {
  /** Whether a message is currently being streamed */
  isStreaming: boolean
  /** Content streamed so far */
  streamingContent: string
  /** Current streaming message ID */
  streamingMessageId: string | null
  /** Error if streaming failed */
  error: Error | null
}

/**
 * Hook for sending messages with streaming support
 *
 * Provides real-time streaming of assistant responses.
 *
 * @example
 * const { sendMessage, isStreaming, streamingContent } = useSendMessage()
 *
 * await sendMessage({
 *   conversationId: 'conv-123',
 *   content: 'Make this more concise',
 *   onChunk: (chunk) => console.log(chunk.content)
 * })
 */
export function useSendMessage() {
  const queryClient = useQueryClient()
  const [state, setState] = useState<SendMessageState>({
    isStreaming: false,
    streamingContent: "",
    streamingMessageId: null,
    error: null,
  })

  // Use ref to avoid stale closure issues
  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (params: {
      conversationId: string
      content: string
      enableWebSearch?: boolean
      model?: string
      onChunk?: (chunk: MessageChunk) => void
    }): Promise<ChatMessage | null> => {
      const { conversationId, content, enableWebSearch, model, onChunk } = params

      // Reset state
      setState({
        isStreaming: true,
        streamingContent: "",
        streamingMessageId: null,
        error: null,
      })

      // Create abort controller
      abortControllerRef.current = new AbortController()

      try {
        // Optimistically add user message to conversation
        const userMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: "user",
          content,
          timestamp: new Date().toISOString(),
        }

        queryClient.setQueryData<Conversation>(
          queryKeys.chat.conversation(conversationId),
          (old) => {
            if (!old) return old
            return {
              ...old,
              messages: [...old.messages, userMessage],
              updatedAt: new Date().toISOString(),
            }
          }
        )

        // Send message and stream response
        const assistantMessage = await sendMessageApi(
          conversationId,
          { content, enableWebSearch, model },
          (chunk) => {
            switch (chunk.type) {
              case "start":
                setState((prev) => ({
                  ...prev,
                  streamingMessageId: chunk.messageId || null,
                }))
                break

              case "delta":
                setState((prev) => ({
                  ...prev,
                  streamingContent: prev.streamingContent + (chunk.content || ""),
                }))
                break

              case "end":
                // Will be handled in the resolved promise
                break

              case "error":
                setState((prev) => ({
                  ...prev,
                  error: new Error(chunk.error || "Streaming failed"),
                  isStreaming: false,
                }))
                break
            }

            // Call user's onChunk callback
            onChunk?.(chunk)
          }
        )

        // Add assistant message to conversation cache
        queryClient.setQueryData<Conversation>(
          queryKeys.chat.conversation(conversationId),
          (old) => {
            if (!old) return old
            return {
              ...old,
              messages: [...old.messages, assistantMessage],
              updatedAt: new Date().toISOString(),
            }
          }
        )

        setState({
          isStreaming: false,
          streamingContent: "",
          streamingMessageId: null,
          error: null,
        })

        return assistantMessage
      } catch (error) {
        const err = error instanceof Error ? error : new Error("Failed to send message")
        setState({
          isStreaming: false,
          streamingContent: "",
          streamingMessageId: null,
          error: err,
        })

        // Remove optimistically added user message on error
        queryClient.setQueryData<Conversation>(
          queryKeys.chat.conversation(conversationId),
          (old) => {
            if (!old) return old
            return {
              ...old,
              messages: old.messages.slice(0, -1),
            }
          }
        )

        return null
      }
    },
    [queryClient]
  )

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort()
    setState({
      isStreaming: false,
      streamingContent: "",
      streamingMessageId: null,
      error: null,
    })
  }, [])

  const reset = useCallback(() => {
    setState({
      isStreaming: false,
      streamingContent: "",
      streamingMessageId: null,
      error: null,
    })
  }, [])

  return {
    sendMessage,
    cancel,
    reset,
    ...state,
  }
}

/**
 * Hook for regenerating the last assistant message
 */
export function useRegenerateMessage() {
  const queryClient = useQueryClient()
  const [state, setState] = useState<SendMessageState>({
    isStreaming: false,
    streamingContent: "",
    streamingMessageId: null,
    error: null,
  })

  const regenerate = useCallback(
    async (params: {
      conversationId: string
      onChunk?: (chunk: MessageChunk) => void
    }): Promise<ChatMessage | null> => {
      const { conversationId, onChunk } = params

      setState({
        isStreaming: true,
        streamingContent: "",
        streamingMessageId: null,
        error: null,
      })

      try {
        // Remove last assistant message from cache (will be replaced)
        queryClient.setQueryData<Conversation>(
          queryKeys.chat.conversation(conversationId),
          (old) => {
            if (!old) return old
            const messages = [...old.messages]
            // Remove last message if it's from assistant
            if (messages.length > 0 && messages[messages.length - 1].role === "assistant") {
              messages.pop()
            }
            return { ...old, messages }
          }
        )

        const newMessage = await regenerateLastMessage(conversationId, (chunk) => {
          if (chunk.type === "delta") {
            setState((prev) => ({
              ...prev,
              streamingContent: prev.streamingContent + (chunk.content || ""),
            }))
          }
          onChunk?.(chunk)
        })

        // Add regenerated message to cache
        queryClient.setQueryData<Conversation>(
          queryKeys.chat.conversation(conversationId),
          (old) => {
            if (!old) return old
            return {
              ...old,
              messages: [...old.messages, newMessage],
              updatedAt: new Date().toISOString(),
            }
          }
        )

        setState({
          isStreaming: false,
          streamingContent: "",
          streamingMessageId: null,
          error: null,
        })

        return newMessage
      } catch (error) {
        const err = error instanceof Error ? error : new Error("Failed to regenerate")
        setState({
          isStreaming: false,
          streamingContent: "",
          streamingMessageId: null,
          error: err,
        })
        return null
      }
    },
    [queryClient]
  )

  return {
    regenerate,
    ...state,
  }
}

/**
 * Hook for applying suggested actions from chat
 */
export function useApplySuggestedAction<T = unknown>() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      conversationId,
      messageId,
      actionIndex,
    }: {
      conversationId: string
      messageId: string
      actionIndex?: number
    }) => applySuggestedAction<T>(conversationId, messageId, actionIndex),
    onSuccess: (_data, { conversationId }) => {
      // Invalidate the artifact that was updated
      // The caller should handle specific artifact cache invalidation
      queryClient.invalidateQueries({
        queryKey: queryKeys.chat.conversation(conversationId),
      })
    },
  })
}

/**
 * Convenience hook for managing a chat session
 *
 * Combines conversation loading, message sending, and state management.
 *
 * @example
 * const chat = useChatSession('summary', summaryId)
 *
 * // Start or continue conversation
 * await chat.startOrContinue()
 *
 * // Send message
 * await chat.send('Make this more actionable')
 *
 * // Access state
 * console.log(chat.messages, chat.isStreaming)
 */
export function useChatSession(artifactType: ArtifactType, artifactId: string) {
  const [conversationId, setConversationId] = useState<string | null>(null)

  // Fetch existing conversations for this artifact
  const { data: existingConversations } = useConversationsForArtifact(
    artifactType,
    artifactId
  )

  // Fetch current conversation if we have an ID
  const { data: conversation, isLoading: isLoadingConversation } = useConversation(
    conversationId || "",
    { enabled: !!conversationId }
  )

  // Mutations
  const { mutateAsync: createNewConversation } = useCreateConversation()
  const { sendMessage, isStreaming, streamingContent, error } = useSendMessage()
  const { regenerate, isStreaming: isRegenerating } = useRegenerateMessage()

  // Start or continue a conversation
  const startOrContinue = useCallback(
    async (initialMessage?: string): Promise<Conversation | null> => {
      // If we have existing conversations, use the most recent one
      if (existingConversations && existingConversations.length > 0) {
        const latest = existingConversations[0]
        setConversationId(latest.id)
        return null // Will be loaded by useConversation
      }

      // Create new conversation
      try {
        const newConv = await createNewConversation({
          artifactType,
          artifactId,
          initialMessage,
        })
        setConversationId(newConv.id)
        return newConv
      } catch {
        return null
      }
    },
    [artifactType, artifactId, existingConversations, createNewConversation]
  )

  // Send a message
  const send = useCallback(
    async (
      content: string,
      options?: { enableWebSearch?: boolean; model?: string }
    ): Promise<ChatMessage | null> => {
      if (!conversationId) {
        // Start conversation first
        const newConv = await startOrContinue(content)
        if (newConv) {
          // Initial message was sent during creation
          return newConv.messages[newConv.messages.length - 1]
        }
        return null
      }

      return sendMessage({
        conversationId,
        content,
        ...options,
      })
    },
    [conversationId, sendMessage, startOrContinue]
  )

  // Regenerate last response
  const regenerateResponse = useCallback(async (): Promise<ChatMessage | null> => {
    if (!conversationId) return null
    return regenerate({ conversationId })
  }, [conversationId, regenerate])

  return {
    // State
    conversationId,
    conversation,
    messages: conversation?.messages || [],
    isLoading: isLoadingConversation,
    isStreaming,
    isRegenerating,
    streamingContent,
    error,
    hasConversation: !!conversationId || (existingConversations?.length || 0) > 0,

    // Actions
    startOrContinue,
    send,
    regenerate: regenerateResponse,
    setConversationId,
  }
}
