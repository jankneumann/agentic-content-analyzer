/**
 * Digest Types
 *
 * TypeScript interfaces for digest entities.
 * These types mirror the backend Python models in src/models/digest.py
 *
 * Digests are the aggregated output combining multiple content summaries
 * into a cohesive document with multi-audience formatting.
 *
 * Field names use snake_case to match the Python backend.
 *
 * @see Backend model: src/models/digest.py
 */

/**
 * Type of digest
 * - daily: Aggregation of a single day's content
 * - weekly: Aggregation of a week's content
 * - sub_digest: Intermediate digest for hierarchical combination
 */
export type DigestType = "daily" | "weekly" | "sub_digest"

/**
 * Digest workflow status
 *
 * Tracks the digest through the review and delivery pipeline.
 */
export type DigestStatus =
  | "PENDING" // Created but not yet generated
  | "GENERATING" // LLM is generating content
  | "COMPLETED" // Generation complete, awaiting review
  | "FAILED" // Generation failed
  | "PENDING_REVIEW" // Ready for human review
  | "APPROVED" // Approved by reviewer
  | "REJECTED" // Rejected by reviewer
  | "DELIVERED" // Sent to recipients

/**
 * Source reference in a digest
 *
 * Links digest content back to original content items.
 */
export interface DigestSource {
  /** Newsletter title */
  title: string
  /** Publication name */
  publication: string | null
  /** Original date */
  date: string
  /** Original URL if available */
  url?: string | null
}

/**
 * Section within a digest
 *
 * Digests are structured into sections, each targeting
 * different aspects of the content.
 */
export interface DigestSection {
  /** Section title */
  title: string
  /** Brief summary of the section */
  summary: string
  /** Detailed points/bullets */
  details: string[]
  /** Related themes */
  themes: string[]
  /**
   * Historical continuity context
   * How this section relates to previous digests
   */
  continuity?: string | null
}

/**
 * Actionable recommendations organized by role
 *
 * Different recommendations for different audience segments.
 */
export interface ActionableRecommendations {
  /** For leadership */
  for_leadership?: string[]
  /** For teams */
  for_teams?: string[]
  /** For individuals */
  for_individuals?: string[]
  [key: string]: string[] | undefined
}

/**
 * Revision history entry
 *
 * Tracks changes made to the digest through the review process.
 */
export interface RevisionEntry {
  /** When the revision was made */
  timestamp: string
  /** Who made the revision */
  reviewer: string
  /** What action was taken */
  action: string
  /** Section-specific feedback */
  section_feedback?: Record<string, string>
}

/**
 * Digest list item (lightweight view)
 *
 * Used in list views - matches backend DigestSummary response model.
 */
export interface DigestListItem {
  id: number
  digest_type: DigestType
  title: string
  period_start: string
  period_end: string
  content_count: number
  status: DigestStatus
  created_at: string
  model_used: string
  revision_count: number
  reviewed_by: string | null
}

/**
 * Digest detail (full view)
 *
 * Used for detail views - matches backend DigestDetail response model.
 */
export interface DigestDetail {
  id: number
  digest_type: DigestType
  title: string
  period_start: string
  period_end: string
  executive_overview: string
  strategic_insights: DigestSection[]
  technical_developments: DigestSection[]
  emerging_trends: DigestSection[]
  actionable_recommendations: ActionableRecommendations
  sources: DigestSource[]
  content_count: number
  status: DigestStatus
  created_at: string
  completed_at: string | null
  model_used: string
  model_version: string | null
  processing_time_seconds: number | null
  revision_count: number
  reviewed_by: string | null
  reviewed_at: string | null
  review_notes: string | null
  is_combined: boolean
  child_digest_ids: number[] | null
}

/**
 * Digest statistics
 */
export interface DigestStatistics {
  total: number
  pending: number
  generating: number
  completed: number
  pending_review: number
  approved: number
  delivered: number
  by_type: Record<string, number>
}

/**
 * Digest entity (full model)
 *
 * The main aggregated output document combining
 * multiple newsletter summaries.
 */
export interface Digest extends DigestDetail {
  /** Historical context from knowledge graph */
  historical_context?: Record<string, unknown>
  /** Agent framework used */
  agent_framework: string
  /** Tokens used */
  token_usage: number | null
  /** Parent digest ID (for sub_digests) */
  parent_digest_id: number | null
  /** Number of source digests if combined */
  source_digest_count: number | null
  /** When delivered */
  delivered_at: string | null
  /** History of revisions */
  revision_history: RevisionEntry[] | null
}

/**
 * Request to generate a new digest
 */
export interface GenerateDigestRequest {
  /** Type of digest to generate */
  digest_type: "daily" | "weekly"
  /** Start of period to cover (optional, computed based on type) */
  period_start?: string
  /** End of period to cover (optional, defaults to now) */
  period_end?: string
  /** Max strategic insights */
  max_strategic_insights?: number
  /** Max technical developments */
  max_technical_developments?: number
  /** Max emerging trends */
  max_emerging_trends?: number
  /** Include historical context from knowledge graph */
  include_historical_context?: boolean
}

/**
 * Review action for a digest
 */
export type ReviewAction = "approve" | "request_revision" | "reject"

/**
 * Section-specific feedback for revision
 */
export interface SectionFeedback {
  /** Section identifier (e.g., "strategic_insights", "emerging_trends") */
  section: string
  /** Specific feedback for this section */
  feedback: string
  /** Index within the section array (if applicable) */
  index?: number
}

/**
 * Request to submit a digest review
 */
export interface DigestReviewRequest {
  /** Review action */
  action: ReviewAction
  /** Name of the reviewer */
  reviewer: string
  /** Section-specific feedback (key = section type, value = feedback) */
  section_feedback?: Record<string, string>
  /** General notes about the review */
  notes?: string
}

/**
 * Request to revise a specific section
 */
export interface ReviseDigestSectionRequest {
  /** Revision instructions */
  feedback: string
}

/**
 * Sort order for table sorting
 */
export type SortOrder = "asc" | "desc"

/**
 * Filters for digest list queries
 */
export interface DigestFilters {
  /** Filter by digest type */
  digest_type?: DigestType
  /** Filter by status */
  status?: DigestStatus
  /** Pagination limit */
  limit?: number
  /** Pagination offset */
  offset?: number
  /** Field to sort by */
  sort_by?: string
  /** Sort direction */
  sort_order?: SortOrder
}

/**
 * Progress event for digest generation (SSE)
 */
export interface DigestGenerationProgress {
  /** Task identifier */
  task_id: string
  /** Current step */
  step: string
  /** Progress percentage (0-100) */
  progress: number
  /** Status */
  status: "processing" | "completed" | "error"
  /** Error message if failed */
  error_message?: string
  /** Digest ID once created */
  digest_id?: number
}
