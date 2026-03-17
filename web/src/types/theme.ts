/**
 * Theme Types
 *
 * TypeScript interfaces for theme analysis entities.
 * These types mirror the backend Python models in src/models/theme.py
 *
 * Theme analysis identifies patterns and topics across multiple content items,
 * tracking how themes evolve over time using the knowledge graph.
 *
 * @see Backend model: src/models/theme.py
 */

/**
 * Theme categories for classification
 *
 * Categories help organize themes into meaningful groups
 * for filtering and navigation.
 */
export type ThemeCategory =
  | "ml_ai" // Machine learning and AI topics
  | "devops_infra" // DevOps, infrastructure, cloud
  | "data_engineering" // Data pipelines, warehousing
  | "business_strategy" // Business and strategy topics
  | "tools_products" // New tools, product launches
  | "research_academia" // Research papers, academic work
  | "security" // Security, privacy, compliance
  | "other" // Uncategorized

/**
 * Theme trend classification
 *
 * Indicates how the theme is evolving over time
 * based on historical mentions in the knowledge graph.
 */
export type ThemeTrend =
  | "emerging" // New topic, first mentions recently
  | "growing" // Increasing frequency of mentions
  | "established" // Consistent, stable presence
  | "declining" // Decreasing frequency
  | "one_off" // Single mention, not recurring

/**
 * Entity from the knowledge graph
 *
 * Represents a node in the Neo4j knowledge graph,
 * extracted and maintained by Graphiti.
 */
export interface Entity {
  /** Unique entity identifier */
  id: string
  /** Entity name/label */
  name: string
  /** Entity type (e.g., "Technology", "Company", "Person") */
  type: string
  /** Additional properties/attributes */
  properties: Record<string, unknown>
}

/**
 * Relationship between entities
 *
 * Represents an edge in the knowledge graph
 * connecting two entities.
 */
export interface Relationship {
  /** Unique relationship identifier */
  id: string
  /** Source entity ID */
  sourceId: string
  /** Target entity ID */
  targetId: string
  /** Relationship type (e.g., "USES", "COMPETES_WITH") */
  type: string
  /** Confidence score (0-1) */
  confidence: number
  /** Additional properties */
  properties: Record<string, unknown>
}

/**
 * Individual theme within an analysis
 *
 * Represents a single identified theme with
 * its classification and supporting data.
 */
export interface Theme {
  /** Theme name/title */
  name: string

  /** Category classification */
  category: ThemeCategory

  /** Trend based on historical data */
  trend: ThemeTrend

  /** Confidence score (0-1) of theme identification */
  confidence: number

  /** Number of mentions across analyzed content items */
  mentions: number

  /** IDs of content items that mention this theme */
  sourceContentIds: string[]

  /** Brief summary of the theme */
  summary: string

  /** Related entities from knowledge graph */
  relatedEntities: Entity[]

  /** Key quotes or excerpts about this theme */
  keyExcerpts: string[]

  /**
   * Historical context from knowledge graph
   * Previous mentions and evolution of this theme
   */
  historicalContext?: {
    /** When theme was first seen */
    firstMention: string
    /** Total historical mentions */
    totalMentions: number
    /** Narrative of how theme has evolved */
    evolutionNarrative: string
  }
}

/**
 * Theme Analysis entity
 *
 * Results of analyzing themes across a set of content items
 * for a specific time period.
 */
export interface ThemeAnalysis {
  /** Unique identifier (UUID) */
  id: string

  /** Date the analysis was performed */
  analysisDate: string // ISO 8601

  /** Start of the analyzed period */
  startDate: string // ISO 8601

  /** End of the analyzed period */
  endDate: string // ISO 8601

  /** Number of content items analyzed */
  contentCount: number

  /** IDs of analyzed content items */
  contentIds: string[]

  /** Identified themes */
  themes: Theme[]

  /** Total number of themes identified */
  totalThemes: number

  /** Count of emerging themes */
  emergingThemesCount: number

  /** Name of the top/most prominent theme */
  topTheme: string

  /** Agent framework used */
  agentFramework: string

  /** Model used for analysis */
  modelUsed: string

  /** Model version */
  modelVersion: string | null

  /** Processing time in seconds */
  processingTimeSeconds: number

  /** Tokens used */
  tokenUsage: number
}

/**
 * Graph data structure for visualization
 *
 * Format suitable for react-force-graph and similar libraries.
 */
export interface GraphData {
  /** Nodes in the graph */
  nodes: GraphNode[]
  /** Links/edges in the graph */
  links: GraphLink[]
}

/**
 * Node in the graph visualization
 */
export interface GraphNode {
  /** Unique node ID */
  id: string
  /** Display label */
  label: string
  /** Node type for coloring/grouping */
  type: "theme" | "entity" | "content"
  /** Optional size weight */
  weight?: number
  /** Category for themes */
  category?: ThemeCategory
  /** Trend for themes */
  trend?: ThemeTrend
  /** Additional display properties */
  properties?: Record<string, unknown>
}

/**
 * Link/edge in the graph visualization
 */
export interface GraphLink {
  /** Source node ID */
  source: string
  /** Target node ID */
  target: string
  /** Relationship type label */
  type: string
  /** Link strength/weight */
  weight?: number
}

/**
 * Request to trigger theme analysis
 */
export interface AnalyzeThemesRequest {
  /** Start date for analysis period */
  startDate: string
  /** End date for analysis period */
  endDate: string
  /** Specific content IDs (if empty, uses date range) */
  contentIds?: string[]
  /** Include historical context from knowledge graph */
  includeHistoricalContext?: boolean
}

/**
 * Filters for theme analysis list
 */
export interface ThemeAnalysisFilters {
  /** Filter by date range start */
  startDate?: string
  /** Filter by date range end */
  endDate?: string
  /** Minimum number of themes */
  minThemes?: number
  /** Pagination limit */
  limit?: number
  /** Pagination offset */
  offset?: number
}

/**
 * Theme data from backend ThemeData model
 */
export interface ThemeData {
  name: string
  description: string
  category: ThemeCategory
  mention_count: number
  content_ids: number[]
  first_seen: string
  last_seen: string
  trend: ThemeTrend
  relevance_score: number
  strategic_relevance: number
  tactical_relevance: number
  novelty_score: number
  cross_functional_impact: number
  related_themes: string[]
  key_points: string[]
  historical_context?: {
    theme_name: string
    first_mention: string
    total_mentions: number
    mention_frequency: string
    evolution_summary: string
    previous_discussions: string[]
    stance_change?: string
    recent_mentions: Array<{
      date: string
      content_id: number
      content_title: string
      publication: string
      context: string
      sentiment?: string
    }>
  }
  continuity_text?: string
}

/**
 * Result from theme analysis (matches backend ThemeAnalysisResult)
 */
export interface ThemeAnalysisResult {
  id: number
  analysis_date: string
  start_date: string
  end_date: string
  content_count: number
  content_ids: number[]
  themes: ThemeData[]
  total_themes: number
  emerging_themes_count: number
  top_theme: string | null
  processing_time_seconds: number
  token_usage: number | null
  model_used: string
  model_version: string | null
  agent_framework: string
  cross_theme_insights: string[]
  error_message?: string
  created_at?: string
}
