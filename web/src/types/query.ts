/**
 * Content Query Types
 *
 * TypeScript interfaces for the ContentQuery builder feature.
 * These types mirror the backend Python models in src/models/query.py
 *
 * @see Backend model: src/models/query.py
 */

import type { ContentSource, ContentStatus, SortOrder } from "./content"

/**
 * Content query filter specification
 *
 * Shared filter model used by summarize and digest operations.
 * Field names use snake_case to match the backend API.
 * Null/undefined values mean "no filter" for that dimension.
 */
export interface ContentQuery {
  /** Filter by source types (null = all sources) */
  source_types?: ContentSource[]
  /** Filter by processing statuses (null = operation default) */
  statuses?: ContentStatus[]
  /** Filter by exact publication names */
  publications?: string[]
  /** Search publication names (ILIKE) */
  publication_search?: string
  /** Content published after this date (ISO 8601) */
  start_date?: string
  /** Content published before this date (ISO 8601) */
  end_date?: string
  /** Search in title (ILIKE) */
  search?: string
  /** Maximum results (must be > 0) */
  limit?: number
  /** Field to sort by */
  sort_by?: string
  /** Sort direction */
  sort_order?: SortOrder
}

/**
 * Preview result from a content query
 *
 * Shows what content would be selected without executing
 * the operation (dry-run semantics).
 */
export interface ContentQueryPreview {
  /** Total matching content count */
  total_count: number
  /** Count by source type (alphabetical keys) */
  by_source: Record<string, number>
  /** Count by status (alphabetical keys) */
  by_status: Record<string, number>
  /** Date range of matching content */
  date_range: {
    earliest?: string
    latest?: string
  }
  /** Sample titles (max 10, ordered by published_date desc) */
  sample_titles: string[]
  /** The query that produced this preview */
  query: ContentQuery
}
