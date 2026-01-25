/**
 * Review System Types
 *
 * TypeScript interfaces for the side-by-side review system.
 * Used for reviewing and providing feedback on summaries, digests, and scripts.
 */

/**
 * A selected text snippet added to the feedback context
 */
export interface ContextItem {
  /** Unique identifier */
  id: string
  /** Selected text content (max 500 chars, truncated) */
  text: string
  /** Which pane the text was selected from */
  source: "left" | "right"
  /** Human-readable label for the source pane */
  paneLabel: string
}

/**
 * Navigation info for prev/next within a filtered list
 */
export interface NavigationInfo {
  /** ID of previous item (null if at start) */
  prevId: number | null
  /** ID of next item (null if at end) */
  nextId: number | null
  /** Current position in list (1-indexed) */
  position: number
  /** Total items in filtered list */
  total: number
}

/**
 * Request to regenerate a summary with feedback
 */
export interface RegenerateWithFeedbackRequest {
  /** User's feedback/instructions for regeneration */
  feedback?: string
  /** Selected text snippets for additional context */
  contextSelections?: Array<{
    text: string
    source: "content" | "summary"
  }>
  /** If true, returns preview without saving */
  previewOnly?: boolean
}

/**
 * Request to commit a previewed summary
 */
export interface CommitPreviewRequest {
  /** The preview content to save */
  executiveSummary: string
  keyThemes: string[]
  strategicInsights: string[]
  technicalDetails: string[]
  actionableItems: string[]
  notableQuotes: string[]
}

/**
 * Practical limits for the review interface
 */
export const REVIEW_LIMITS = {
  /** Maximum number of context selections */
  MAX_CONTEXT_ITEMS: 5,
  /** Maximum characters per selection */
  MAX_CHARS_PER_SELECTION: 500,
  /** Maximum total context characters */
  MAX_TOTAL_CONTEXT_CHARS: 2000,
  /** Maximum feedback input length */
  MAX_FEEDBACK_LENGTH: 1000,
} as const

/**
 * Review type discriminator
 */
export type ReviewType = "summary" | "digest" | "script"

/**
 * Props for the ReviewLayout component
 */
export interface ReviewLayoutProps {
  /** Content for the left pane (source) */
  leftPane: React.ReactNode
  /** Content for the right pane (generated) */
  rightPane: React.ReactNode
  /** Feedback panel at the bottom */
  feedbackPanel?: React.ReactNode
  /** Header with navigation */
  header?: React.ReactNode
}

/**
 * Props for the ReviewHeader component
 */
export interface ReviewHeaderProps {
  /** Title for the review page */
  title: string
  /** Label for the back button */
  backLabel: string
  /** URL to navigate back to */
  backTo: string
  /** Navigation info for prev/next */
  navigation?: NavigationInfo
  /** Loading state for navigation */
  isNavigationLoading?: boolean
  /** Callback when prev is clicked */
  onPrevious?: () => void
  /** Callback when next is clicked */
  onNext?: () => void
}

/**
 * Props for ContentPane component
 */
export interface ContentPaneProps {
  /** Unique identifier for this pane */
  paneId: "left" | "right"
  /** Human-readable label for this pane */
  paneLabel: string
  /** Content to render */
  children: React.ReactNode
  /** Additional CSS classes */
  className?: string
  /** Whether selection is enabled */
  selectionEnabled?: boolean
}

/**
 * Dialogue turn in a script section
 */
export interface ScriptDialogueTurn {
  speaker: string
  text: string
  emphasis: string | null
  pause_after: number | null
}

/**
 * A section in a podcast script
 */
export interface ScriptSection {
  index: number
  type: "intro" | "strategic" | "technical" | "trend" | "outro"
  title: string
  word_count: number
  dialogue: ScriptDialogueTurn[]
  sources_cited: string[]
}

/**
 * Source summary referenced by a script
 */
export interface ScriptSourceRef {
  id: string
  title: string
  publication: string | null
  url?: string
}

/**
 * Full script detail for review
 */
export interface ScriptDetail {
  id: number
  digest_id: number
  title: string
  length: string
  word_count: number
  estimated_duration: string
  estimated_duration_seconds: number
  status: string
  revision_count: number
  created_at: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  sections: ScriptSection[]
  sources_summary: ScriptSourceRef[]
  revision_history: Array<{
    timestamp: string
    revised_by: string
    sections_revised: number[]
    feedback: string
  }>
  content_ids_fetched: string[]
  web_search_queries: string[]
  tool_call_count: number
}
