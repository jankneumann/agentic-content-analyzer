/**
 * Digest Types
 *
 * TypeScript interfaces for digest entities.
 * These types mirror the backend Python models in src/models/digest.py
 *
 * Digests are the aggregated output combining multiple newsletter summaries
 * into a cohesive document with multi-audience formatting.
 *
 * @see Backend model: src/models/digest.py
 */

/**
 * Type of digest
 * - daily: Aggregation of a single day's newsletters
 * - weekly: Aggregation of a week's newsletters
 * - sub_digest: Intermediate digest for hierarchical combination
 */
export type DigestType = "daily" | "weekly" | "sub_digest"

/**
 * Digest workflow status
 *
 * Tracks the digest through the review and delivery pipeline.
 */
export type DigestStatus =
  | "pending" // Created but not yet generated
  | "generating" // LLM is generating content
  | "completed" // Generation complete, awaiting review
  | "failed" // Generation failed
  | "pending_review" // Ready for human review
  | "approved" // Approved by reviewer
  | "rejected" // Rejected by reviewer
  | "delivered" // Sent to recipients

/**
 * Source reference in a digest
 *
 * Links digest content back to original newsletters.
 */
export interface DigestSource {
  /** Newsletter ID */
  id: string
  /** Newsletter title */
  title: string
  /** Publication name */
  publication: string | null
  /** Original URL if available */
  url?: string
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
  continuity?: string
}

/**
 * Actionable recommendations organized by role
 *
 * Different recommendations for different audience segments.
 */
export interface ActionableRecommendations {
  /** For executives/leadership */
  executives?: string[]
  /** For engineering leaders */
  engineeringLeaders?: string[]
  /** For individual contributors */
  practitioners?: string[]
  /** General recommendations */
  general?: string[]
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
  revisedBy: string
  /** What sections were changed */
  sectionsChanged: string[]
  /** Feedback that prompted the revision */
  feedback: string
  /** Summary of changes made */
  changesSummary: string
}

/**
 * Digest entity
 *
 * The main aggregated output document combining
 * multiple newsletter summaries.
 */
export interface Digest {
  /** Unique identifier (UUID) */
  id: string

  /** Type of digest */
  digestType: DigestType

  /** Start of the covered period */
  periodStart: string // ISO 8601

  /** End of the covered period */
  periodEnd: string // ISO 8601

  /** Digest title */
  title: string

  /**
   * Executive overview
   * High-level summary for leadership (2-3 paragraphs)
   */
  executiveOverview: string

  /**
   * Strategic insights section
   * CTO-level implications and recommendations
   */
  strategicInsights: DigestSection[]

  /**
   * Technical developments section
   * Developer-focused details and implementations
   */
  technicalDevelopments: DigestSection[]

  /**
   * Emerging trends section
   * New topics with historical context
   */
  emergingTrends: DigestSection[]

  /**
   * Role-specific action items
   */
  actionableRecommendations: ActionableRecommendations

  /**
   * Source newsletters referenced
   */
  sources: DigestSource[]

  /**
   * Historical context from knowledge graph
   */
  historicalContext?: Record<string, unknown>

  /** Number of newsletters included */
  newsletterCount: number

  /** Current status in workflow */
  status: DigestStatus

  /** Who reviewed/approved */
  reviewedBy: string | null

  /** Review notes */
  reviewNotes: string | null

  /** When reviewed */
  reviewedAt: string | null

  /** Number of revisions made */
  revisionCount: number

  /** History of revisions */
  revisionHistory: RevisionEntry[]

  /** Parent digest ID (for sub_digests) */
  parentDigestId: string | null

  /** Child digest IDs (for combined digests) */
  childDigestIds: string[]

  /** Whether this is a combined digest */
  isCombined: boolean

  /** Number of source digests if combined */
  sourceDigestCount: number

  /** Agent framework used */
  agentFramework: string

  /** Model used */
  modelUsed: string

  /** Model version */
  modelVersion: string | null

  /** Tokens used */
  tokenUsage: number

  /** Processing time in seconds */
  processingTimeSeconds: number

  /** When created */
  createdAt: string // ISO 8601

  /** When generation completed */
  completedAt: string | null

  /** When delivered */
  deliveredAt: string | null
}

/**
 * Digest list item (lightweight view)
 */
export interface DigestListItem {
  id: string
  digestType: DigestType
  title: string
  periodStart: string
  periodEnd: string
  newsletterCount: number
  status: DigestStatus
  reviewedBy: string | null
  revisionCount: number
  createdAt: string
}

/**
 * Request to generate a new digest
 */
export interface GenerateDigestRequest {
  /** Type of digest to generate */
  digestType: DigestType
  /** Start of period to cover */
  periodStart: string
  /** End of period to cover */
  periodEnd: string
  /** Specific newsletter IDs (optional, uses date range if not provided) */
  newsletterIds?: string[]
  /** Include historical context from knowledge graph */
  includeHistoricalContext?: boolean
  /** Custom title (auto-generated if not provided) */
  title?: string
}

/**
 * Review action for a digest
 */
export type ReviewAction = "approve" | "request_revision" | "reject"

/**
 * Section-specific feedback for revision
 */
export interface SectionFeedback {
  /** Section identifier (e.g., "strategicInsights", "emergingTrends") */
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
  /** Section-specific feedback */
  sectionFeedback?: SectionFeedback[]
  /** General notes about the review */
  generalNotes?: string
}

/**
 * Request to revise a specific section
 */
export interface ReviseDigestSectionRequest {
  /** Section to revise */
  section: string
  /** Index within section array */
  index: number
  /** Revision instructions */
  feedback: string
  /** Reviewer name */
  reviewer: string
}

/**
 * Filters for digest list queries
 */
export interface DigestFilters {
  /** Filter by digest type */
  digestType?: DigestType
  /** Filter by status */
  status?: DigestStatus
  /** Filter by period start (after this date) */
  periodStartAfter?: string
  /** Filter by period end (before this date) */
  periodEndBefore?: string
  /** Filter by reviewer */
  reviewedBy?: string
  /** Pagination limit */
  limit?: number
  /** Pagination offset */
  offset?: number
}

/**
 * Progress event for digest generation (SSE)
 */
export interface DigestGenerationProgress {
  /** Task identifier */
  taskId: string
  /** Current step */
  step: string
  /** Progress percentage (0-100) */
  progress: number
  /** Status */
  status: "processing" | "completed" | "error"
  /** Error message if failed */
  errorMessage?: string
  /** Digest ID once created */
  digestId?: string
}
