/**
 * Summary Types
 *
 * TypeScript interfaces for content summary entities.
 * Summaries are linked to Content records (unified model).
 *
 * @see Backend model: src/models/summary.py
 */

/**
 * Content Summary entity
 *
 * Contains structured information extracted from content by the LLM.
 * Each content has at most one summary (1:1 relationship).
 */
export interface NewsletterSummary {
  /** Unique identifier */
  id: number

  /** ID of the content this summary belongs to */
  content_id: number

  /**
   * Executive summary - 2-3 sentence high-level overview
   * Suitable for leadership or quick scanning
   */
  executive_summary: string

  /**
   * Key themes identified in the content
   * Array of theme names/topics covered
   */
  key_themes: string[]

  /**
   * Strategic insights for business leaders
   * Higher-level implications and recommendations
   */
  strategic_insights: string[]

  /**
   * Technical details for practitioners
   * Implementation notes, code references, technical depth
   */
  technical_details: string[]

  /**
   * Actionable items extracted from the content
   * Things readers could implement or investigate
   */
  actionable_items: string[]

  /**
   * Notable quotes from the content
   * Interesting or impactful statements
   */
  notable_quotes: string[]

  /**
   * Relevant links for further reading
   * URLs mentioned in the content worth highlighting
   */
  relevant_links: Array<Record<string, unknown>>

  /**
   * Relevance scores for different audience segments
   */
  relevance_scores: {
    cto_leadership: number
    technical_teams: number
    individual_developers: number
  }

  /**
   * Agent framework used for summarization
   * e.g., "claude-sdk", "langchain", "autogen"
   */
  agent_framework: string

  /**
   * LLM model identifier used
   * e.g., "claude-haiku-4-5", "gpt-4o"
   */
  model_used: string

  /**
   * Specific model version (if available)
   */
  model_version: string | null

  /** When the summary was created */
  created_at: string // ISO 8601 date string

  /** Total tokens used in generation */
  token_usage: number | null

  /** Time taken to generate in seconds */
  processing_time_seconds: number | null
}

/**
 * Summary list item (lightweight view)
 *
 * For displaying in lists without full content.
 */
export interface SummaryListItem {
  id: number
  /** Content ID this summary belongs to */
  content_id: number
  /** Content title for display */
  title: string
  /** Content publication name */
  publication: string | null
  /** First 200 chars of executive summary */
  executive_summary_preview: string
  key_themes: string[]
  model_used: string
  created_at: string
  processing_time_seconds: number | null
}

/**
 * Progress event for summarization task (SSE)
 */
export interface SummarizationProgress {
  /** Task identifier */
  task_id: string
  /** Current step description */
  step?: string
  /** Progress percentage (0-100) */
  progress: number
  /** Currently processing content ID */
  current_content_id?: number
  /** Count of completed summaries */
  completed_count?: number
  /** Total count to process */
  total_count?: number
  /** Count of processed */
  processed?: number
  /** Total */
  total?: number
  /** Status: processing, completed, or error */
  status: "queued" | "processing" | "completed" | "error"
  /** Message from the server */
  message?: string
}

/**
 * Filters for summary list queries
 */
export interface SummaryFilters {
  /** Filter by content ID */
  content_id?: number
  /** Filter by model used */
  model_used?: string
  /** Filter after this date */
  start_date?: string
  /** Filter before this date */
  end_date?: string
  /** Pagination limit */
  limit?: number
  /** Pagination offset */
  offset?: number
}

/**
 * Navigation response for prev/next within a filtered list
 */
export interface SummaryNavigation {
  prev_id: number | null
  next_id: number | null
  prev_content_id: number | null
  next_content_id: number | null
  position: number
  total: number
}
