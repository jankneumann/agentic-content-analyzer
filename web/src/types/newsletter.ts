/**
 * Newsletter Types - DEPRECATED
 *
 * @deprecated This entire module is deprecated. Use Content types from './content.ts' instead.
 *
 * These types are now aliases to Content types for backward compatibility.
 * All new code should import from './content.ts' directly.
 *
 * Migration guide:
 * - Newsletter → Content
 * - NewsletterSource → ContentSource
 * - NewsletterStatus → ContentStatus
 * - NewsletterListItem → ContentListItem
 * - NewsletterFilters → ContentFilters
 * - IngestRequest → ContentFilters (for ingestion params)
 *
 * @see openspec/changes/deprecate-newsletter-model/ for deprecation plan
 * @see Backend model: src/models/content.py (new unified model)
 */

import type {
  Content,
  ContentSource,
  ContentStatus,
  ContentListItem,
  ContentFilters,
} from "./content"

/**
 * Source of the newsletter content
 * @deprecated Use ContentSource from './content.ts' instead
 */
export type NewsletterSource = ContentSource

/**
 * Processing status of a newsletter
 * @deprecated Use ContentStatus from './content.ts' instead
 */
export type NewsletterStatus = ContentStatus

/**
 * Link extracted from newsletter content
 * @deprecated Use links_json from Content instead
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
 * This type is an alias to Content for backward compatibility.
 * Field mapping:
 * - source → source_type
 * - sender → author
 * - raw_html/raw_text → markdown_content
 * - canonical_newsletter_id → canonical_id
 */
export type Newsletter = Content

/**
 * Newsletter list item (summary view)
 *
 * @deprecated Use ContentListItem from './content.ts' instead.
 */
export type NewsletterListItem = ContentListItem

/**
 * Filters for newsletter list queries
 * @deprecated Use ContentFilters from './content.ts' instead.
 */
export type NewsletterFilters = ContentFilters

/**
 * Request to trigger newsletter ingestion
 * @deprecated Use the content ingestion API instead.
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
 * @deprecated Use the content ingestion API response instead.
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
