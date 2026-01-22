/**
 * Content Types
 *
 * TypeScript interfaces for the unified Content model.
 * These types mirror the backend Python models in src/models/content.py
 *
 * The Content model unifies newsletters, documents, and other content sources
 * into a single entity with markdown-first representation.
 *
 * @see Backend model: src/models/content.py
 */

/**
 * Source of the content
 * - gmail: Fetched from Gmail inbox
 * - rss: Fetched from RSS feed
 * - file_upload: Uploaded document (PDF, DOCX, etc.)
 * - youtube: YouTube video transcript
 * - manual: Manually created via API
 * - webpage: Scraped web page (future)
 * - other: Other sources
 */
export type ContentSource =
  | "gmail"
  | "rss"
  | "file_upload"
  | "youtube"
  | "manual"
  | "webpage"
  | "other"

/**
 * Processing status of content
 * - pending: Awaiting processing
 * - parsing: Being parsed to markdown
 * - parsed: Successfully parsed
 * - processing: Being summarized
 * - completed: Successfully processed
 * - failed: Processing encountered an error
 */
export type ContentStatus =
  | "pending"
  | "parsing"
  | "parsed"
  | "processing"
  | "completed"
  | "failed"

/**
 * Content entity
 *
 * Represents a single piece of content that has been ingested.
 * This is the unified model replacing Newsletter + Document.
 * Field names use snake_case to match the Python backend API responses.
 */
export interface Content {
  /** Unique identifier */
  id: number

  /** Source type of the content */
  source_type: ContentSource

  /** External ID from the source system */
  source_id: string

  /** Original URL if available */
  source_url: string | null

  /** Title of the content */
  title: string

  /** Author or sender */
  author: string | null

  /** Publication name if available */
  publication: string | null

  /** When the content was originally published */
  published_date: string | null // ISO 8601 date string

  /** Content in markdown format (primary content field) */
  markdown_content: string

  /** Structured table data extracted from content */
  tables_json: Record<string, unknown>[] | null

  /** URLs extracted from content */
  links_json: string[] | null

  /** Additional metadata */
  metadata_json: Record<string, unknown> | null

  /** Parser used to process the content */
  parser_used: string | null

  /** SHA-256 hash for deduplication */
  content_hash: string

  /** Canonical content ID if this is a duplicate */
  canonical_id: number | null

  /** Current processing status */
  status: ContentStatus

  /** Error message if status is 'failed' */
  error_message: string | null

  /** When the content was ingested into the system */
  ingested_at: string // ISO 8601 date string

  /** When parsing completed */
  parsed_at: string | null

  /** When processing completed */
  processed_at: string | null

  /** Legacy newsletter ID for navigating to summary review.
   * During migration, content is linked to newsletters via source_id.
   * This field provides direct access to the newsletter_id for summary lookups. */
  legacy_newsletter_id: number | null
}

/**
 * Content list item (summary view)
 *
 * Lightweight representation for list views.
 * Omits large fields like markdown_content.
 */
export interface ContentListItem {
  id: number
  source_type: ContentSource
  title: string
  publication: string | null
  published_date: string | null
  status: ContentStatus
  ingested_at: string
  /** Legacy newsletter ID for navigating to summary review */
  legacy_newsletter_id: number | null
}

/**
 * Paginated content list response
 */
export interface ContentListResponse {
  items: ContentListItem[]
  total: number
  page: number
  page_size: number
  has_next: boolean
  has_prev: boolean
}

/**
 * Sort order for table sorting
 */
export type SortOrder = "asc" | "desc"

/**
 * Filters for content list queries
 */
export interface ContentFilters {
  /** Filter by source type */
  source_type?: ContentSource
  /** Filter by processing status */
  status?: ContentStatus
  /** Filter by publication name */
  publication?: string
  /** Filter content after this date */
  start_date?: string
  /** Filter content before this date */
  end_date?: string
  /** Search in title */
  search?: string
  /** Page number (1-indexed) */
  page?: number
  /** Items per page */
  page_size?: number
  /** Field to sort by */
  sort_by?: string
  /** Sort direction */
  sort_order?: SortOrder
}

/**
 * Content statistics
 */
export interface ContentStats {
  total: number
  by_status: Record<ContentStatus, number>
  by_source: Record<ContentSource, number>
  pending_count: number
  completed_count: number
  failed_count: number
  /** Count of content items that don't have summaries yet */
  needs_summarization_count: number
}

/**
 * Request to create content via API
 */
export interface ContentCreateRequest {
  source_type?: ContentSource
  source_id?: string
  source_url?: string
  title: string
  author?: string
  publication?: string
  published_date?: string
  markdown_content: string
  tables_json?: Record<string, unknown>[]
  links_json?: string[]
  metadata_json?: Record<string, unknown>
}

/**
 * Duplicate content information
 */
export interface ContentDuplicateInfo {
  canonical_id: number
  canonical_title: string
  duplicate_count: number
}
