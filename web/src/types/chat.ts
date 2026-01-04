/**
 * Chat Types
 *
 * TypeScript interfaces for the AI revision chatbot.
 * These types support the conversational interface for
 * refining summaries, digests, and scripts.
 *
 * The chat system provides context-aware conversations
 * with artifact grounding and optional web search.
 */

/**
 * Type of artifact the conversation is about
 */
export type ArtifactType = "summary" | "digest" | "script"

/**
 * Role of message sender
 */
export type MessageRole = "user" | "assistant" | "system"

/**
 * Chat message metadata
 *
 * Additional information about how the message was generated.
 */
export interface MessageMetadata {
  /** Model used for generation (assistant messages) */
  model?: string
  /** Tokens used */
  tokenUsage?: number
  /** Whether web search was used */
  webSearchUsed?: boolean
  /** Web search queries made */
  webSearchQueries?: string[]
  /** Processing time in ms */
  processingTimeMs?: number
}

/**
 * Individual chat message
 */
export interface ChatMessage {
  /** Unique message identifier */
  id: string
  /** Sender role */
  role: MessageRole
  /** Message content (markdown supported) */
  content: string
  /** When sent */
  timestamp: string // ISO 8601
  /** Generation metadata */
  metadata?: MessageMetadata
}

/**
 * Conversation entity
 *
 * A chat session tied to a specific artifact for revision.
 */
export interface Conversation {
  /** Unique identifier (UUID) */
  id: string

  /** Type of artifact being discussed */
  artifactType: ArtifactType

  /** ID of the artifact */
  artifactId: string

  /** Conversation title (auto-generated or user-defined) */
  title: string

  /** Messages in the conversation */
  messages: ChatMessage[]

  /** When created */
  createdAt: string // ISO 8601

  /** When last updated */
  updatedAt: string // ISO 8601

  /** Whether conversation is active */
  isActive: boolean
}

/**
 * Conversation list item (lightweight view)
 */
export interface ConversationListItem {
  id: string
  artifactType: ArtifactType
  artifactId: string
  title: string
  messageCount: number
  lastMessagePreview: string
  createdAt: string
  updatedAt: string
}

/**
 * Request to create a new conversation
 */
export interface CreateConversationRequest {
  /** Type of artifact */
  artifactType: ArtifactType
  /** Artifact ID */
  artifactId: string
  /** Optional initial message */
  initialMessage?: string
  /** Optional title */
  title?: string
}

/**
 * Request to send a message
 */
export interface SendMessageRequest {
  /** Message content */
  content: string
  /** Enable web search for this message */
  enableWebSearch?: boolean
  /** Model to use (overrides default) */
  model?: string
}

/**
 * Streaming message chunk (for WebSocket/SSE)
 */
export interface MessageChunk {
  /** Chunk type */
  type: "start" | "delta" | "end" | "error"
  /** Message ID (set on start) */
  messageId?: string
  /** Content delta */
  content?: string
  /** Final metadata (set on end) */
  metadata?: MessageMetadata
  /** Error message (set on error) */
  error?: string
}

/**
 * Suggested action from the assistant
 *
 * The AI may suggest specific changes that can be
 * applied directly to the artifact.
 */
export interface SuggestedAction {
  /** Action type */
  type: "replace_section" | "add_content" | "remove_content" | "rewrite"
  /** Target section (if applicable) */
  section?: string
  /** Section index (if applicable) */
  sectionIndex?: number
  /** Original content */
  originalContent?: string
  /** Suggested new content */
  suggestedContent: string
  /** Explanation of the change */
  explanation: string
}

/**
 * Chat configuration options
 */
export interface ChatConfig {
  /** Available models for selection */
  availableModels: {
    id: string
    name: string
    provider: string
  }[]
  /** Default model */
  defaultModel: string
  /** Whether web search is enabled */
  webSearchEnabled: boolean
  /** Maximum message length */
  maxMessageLength: number
  /** Maximum conversation history length */
  maxHistoryLength: number
}
