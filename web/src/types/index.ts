/**
 * Type Exports
 *
 * Central export point for all TypeScript types.
 * Import types from here for cleaner imports:
 *
 * @example
 * import { Newsletter, Digest, PodcastScript } from '@/types'
 */

// Newsletter types
export type {
  NewsletterSource,
  NewsletterStatus,
  ExtractedLink,
  Newsletter,
  NewsletterListItem,
  NewsletterFilters,
  IngestRequest,
  IngestResponse,
} from "./newsletter"

// Summary types
export type {
  NewsletterSummary,
  SummaryListItem,
  SummarizeRequest,
  SummarizeResponse,
  SummarizationProgress,
  SummaryFilters,
} from "./summary"

// Theme types
export type {
  ThemeCategory,
  ThemeTrend,
  Entity,
  Relationship,
  Theme,
  ThemeAnalysis,
  GraphData,
  GraphNode,
  GraphLink,
  AnalyzeThemesRequest,
  ThemeAnalysisFilters,
} from "./theme"

// Digest types
export type {
  DigestType,
  DigestStatus,
  DigestSource,
  DigestSection,
  ActionableRecommendations,
  RevisionEntry,
  Digest,
  DigestDetail,
  DigestListItem,
  DigestStatistics,
  GenerateDigestRequest,
  ReviewAction,
  SectionFeedback,
  DigestReviewRequest,
  ReviseDigestSectionRequest,
  DigestFilters,
  DigestGenerationProgress,
} from "./digest"

// Podcast types
export type {
  ScriptLength,
  ScriptStatus,
  AudioStatus,
  Speaker,
  DialogueEmphasis,
  SectionType,
  DialogueTurn,
  PodcastSection,
  ScriptSource,
  PodcastScript,
  PodcastScriptRecord,
  ScriptRevisionEntry,
  ScriptListItem,
  Podcast,
  PodcastListItem,
  GenerateScriptRequest,
  ScriptReviewAction,
  ScriptReviewRequest,
  ReviseScriptSectionRequest,
  GenerateAudioRequest,
  AudioGenerationProgress,
  ScriptReviewStatistics,
} from "./podcast"

// Chat types
export type {
  ArtifactType,
  MessageRole,
  MessageMetadata,
  ChatMessage,
  Conversation,
  ConversationListItem,
  CreateConversationRequest,
  SendMessageRequest,
  MessageChunk,
  SuggestedAction,
  ChatConfig,
} from "./chat"

/**
 * Common API response wrapper
 *
 * Standard response format for paginated lists.
 * Field names use snake_case to match the Python backend.
 */
export interface PaginatedResponse<T> {
  /** Data items */
  items: T[]
  /** Total count (without pagination) */
  total: number
  /** Current page offset */
  offset: number
  /** Page size limit */
  limit: number
  /** Whether there are more items */
  has_more: boolean
}

/**
 * API error response
 */
export interface ApiError {
  /** Error message */
  message: string
  /** Error code */
  code: string
  /** Additional details */
  details?: Record<string, unknown>
}

/**
 * Generic task response for async operations
 */
export interface TaskResponse {
  /** Task ID for tracking */
  taskId: string
  /** Task status */
  status: "queued" | "processing" | "completed" | "failed"
  /** Status message */
  message: string
}
