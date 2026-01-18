/**
 * Newsletter Types
 *
 * @deprecated This entire module is deprecated. Use Content types from './content.ts' instead.
 *
 * TypeScript interfaces for newsletter-related entities.
 * These types mirror the backend Python models in src/models/newsletter.py
 *
 * Migration guide:
 * - Newsletter → Content
 * - NewsletterSource → ContentSource
 * - NewsletterStatus → ContentStatus
 * - NewsletterListItem → ContentListItem
 * - NewsletterFilters → ContentFilters
 *
 * @see openspec/changes/deprecate-newsletter-model/ for deprecation plan
 * @see Backend model: src/models/content.py (new unified model)
 */

/**
 * Source of the newsletter content
 * @deprecated Use ContentSource from './content.ts' instead
 */
export type NewsletterSource = "gmail" | "rss" | "youtube"

/**
 * Processing status of a newsletter
 * @deprecated Use ContentStatus from './content.ts' instead
 */
export type NewsletterStatus = "pending" | "processing" | "completed" | "failed"

/**
 * Link extracted from newsletter content
 * Represents a hyperlink found in the newsletter body
 * @deprecated Use ExtractedLink from './content.ts' instead
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
 * @deprecated Use Content from './content.ts' instead.
 *
 * Represents a single newsletter or email that has been ingested.
 * This is the primary content source for the aggregation pipeline.
 * Field names use snake_case to match the Python backend API responses.
 */
export interface Newsletter {
  /** Unique identifier */
  id: number

  /** Source of the newsletter */
  source: NewsletterSource

  /** External ID from the source system (e.g., Gmail message ID) */
  source_id: string

  /** Subject line or title of the newsletter */
  title: string

  /** Sender email address or name */
  sender: string | null

  /** Publication name if available (e.g., "The Batch", "TLDR AI") */
  publication: string | null

  /** When the newsletter was originally published/sent */
  published_date: string // ISO 8601 date string

  /** URL if available */
  url: string | null

  /** Raw HTML content of the newsletter */
  raw_html: string | null

  /** Plain text extraction of content */
  raw_text: string | null

  /** Links extracted from the content */
  extracted_links: string[] | null

  /** SHA-256 hash for deduplication */
  content_hash: string | null

  /** Canonical newsletter ID */
  canonical_newsletter_id: number | null

  /** Current processing status */
  status: NewsletterStatus

  /** When the newsletter was ingested into the system */
  ingested_at: string // ISO 8601 date string

  /** When processing completed (if applicable) */
  processed_at: string | null

  /** Error message if status is 'failed' */
  error_message: string | null
}

/**
 * Newsletter list item (summary view)
 *
 * @deprecated Use ContentListItem from './content.ts' instead.
 *
 * Lightweight representation for list views.
 * Omits large fields like rawHtml and rawText.
 */
export interface NewsletterListItem {
  id: number
  source: NewsletterSource
  title: string
  sender: string | null
  publication: string | null
  published_date: string
  status: NewsletterStatus
  ingested_at: string
  /** Whether a summary exists for this newsletter */
  has_summary: boolean
}

/**
 * Filters for newsletter list queries
 * @deprecated Use ContentFilters from './content.ts' instead.
 */
export interface NewsletterFilters {
  /** Filter by processing status */
  status?: NewsletterStatus
  /** Filter by source type */
  source?: NewsletterSource
  /** Filter by publication name */
  publication?: string
  /** Filter newsletters after this date */
  start_date?: string
  /** Filter newsletters before this date */
  end_date?: string
  /** Search in title and sender */
  search?: string
  /** Number of items to return */
  limit?: number
  /** Offset for pagination */
  offset?: number
}

/**
 * Request to trigger newsletter ingestion
 * @deprecated Use IngestContentRequest from './content.ts' instead.
 */
export interface IngestRequest {
  /** Source to ingest from */
  source: NewsletterSource
  /** Maximum results to fetch */
  max_results?: number
  /** Days back to search */
  days_back?: number
}

/**
 * Response from ingestion trigger
 * @deprecated Use IngestContentResponse from './content.ts' instead.
 */
export interface IngestResponse {
  /** Task ID for tracking progress */
  task_id: string
  /** Message from the server */
  message: string
  /** Source being ingested */
  source: NewsletterSource
  /** Maximum results */
  max_results: number
}
