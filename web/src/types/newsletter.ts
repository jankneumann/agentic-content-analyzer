/**
 * Newsletter Types
 *
 * TypeScript interfaces for newsletter-related entities.
 * These types mirror the backend Python models in src/models/newsletter.py
 *
 * @see Backend model: src/models/newsletter.py
 */

/**
 * Source of the newsletter content
 * - gmail: Fetched from Gmail inbox
 * - rss: Fetched from RSS/Substack feed
 */
export type NewsletterSource = "gmail" | "rss"

/**
 * Processing status of a newsletter
 * - pending: Awaiting processing
 * - processing: Currently being summarized
 * - completed: Successfully processed
 * - failed: Processing encountered an error
 */
export type NewsletterStatus = "pending" | "processing" | "completed" | "failed"

/**
 * Link extracted from newsletter content
 * Represents a hyperlink found in the newsletter body
 */
export interface ExtractedLink {
  /** Display text of the link */
  text: string
  /** URL the link points to */
  url: string
  /** Optional context around where the link was found */
  context?: string
}

/**
 * Newsletter entity
 *
 * Represents a single newsletter or email that has been ingested.
 * This is the primary content source for the aggregation pipeline.
 */
export interface Newsletter {
  /** Unique identifier (UUID) */
  id: string

  /** Source of the newsletter */
  source: NewsletterSource

  /** External ID from the source system (e.g., Gmail message ID) */
  sourceId: string

  /** Subject line or title of the newsletter */
  title: string

  /** Sender email address or name */
  sender: string

  /** Publication name if available (e.g., "The Batch", "TLDR AI") */
  publication: string | null

  /** When the newsletter was originally published/sent */
  publishedDate: string // ISO 8601 date string

  /** Raw HTML content of the newsletter */
  rawHtml: string | null

  /** Plain text extraction of content */
  rawText: string | null

  /** Links extracted from the content */
  extractedLinks: ExtractedLink[]

  /** SHA-256 hash for deduplication */
  contentHash: string

  /** Current processing status */
  status: NewsletterStatus

  /** When the newsletter was ingested into the system */
  ingestedAt: string // ISO 8601 date string

  /** When processing completed (if applicable) */
  processedAt: string | null

  /** Error message if status is 'failed' */
  errorMessage: string | null
}

/**
 * Newsletter list item (summary view)
 *
 * Lightweight representation for list views.
 * Omits large fields like rawHtml and rawText.
 */
export interface NewsletterListItem {
  id: string
  source: NewsletterSource
  title: string
  sender: string
  publication: string | null
  publishedDate: string
  status: NewsletterStatus
  ingestedAt: string
  /** Whether a summary exists for this newsletter */
  hasSummary: boolean
}

/**
 * Filters for newsletter list queries
 */
export interface NewsletterFilters {
  /** Filter by processing status */
  status?: NewsletterStatus
  /** Filter by source type */
  source?: NewsletterSource
  /** Filter by publication name */
  publication?: string
  /** Filter newsletters after this date */
  startDate?: string
  /** Filter newsletters before this date */
  endDate?: string
  /** Search in title and sender */
  search?: string
  /** Number of items to return */
  limit?: number
  /** Offset for pagination */
  offset?: number
}

/**
 * Request to trigger newsletter ingestion
 */
export interface IngestRequest {
  /** Source to ingest from */
  source: NewsletterSource
  /** For RSS: specific feed URL (optional, uses configured feeds if not provided) */
  feedUrl?: string
  /** Maximum number of items to fetch */
  maxItems?: number
}

/**
 * Response from ingestion trigger
 */
export interface IngestResponse {
  /** Number of new newsletters ingested */
  ingestedCount: number
  /** Number of duplicates skipped */
  skippedCount: number
  /** IDs of newly ingested newsletters */
  newsletterIds: string[]
  /** Any errors encountered during ingestion */
  errors: string[]
}
