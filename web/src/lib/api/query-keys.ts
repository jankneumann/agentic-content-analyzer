/**
 * Query Keys Factory
 *
 * Centralized query key definitions for TanStack Query.
 * Using a factory pattern ensures consistent key structure
 * across the application and makes cache invalidation predictable.
 *
 * Key structure follows the pattern: [entity, scope, ...params]
 * - entity: The data type (e.g., 'contents', 'summaries')
 * - scope: The operation scope (e.g., 'list', 'detail', 'infinite')
 * - params: Additional parameters for uniqueness
 *
 * @example
 * // Use in useQuery
 * const { data } = useQuery({
 *   queryKey: queryKeys.contents.list(filters),
 *   queryFn: () => fetchContents(filters),
 * })
 *
 * @example
 * // Invalidate all content queries
 * queryClient.invalidateQueries({ queryKey: queryKeys.contents.all })
 */

import type {
  ContentFilters,
  SummaryFilters,
  DigestFilters,
  AudioDigestFilters,
} from "@/types"

/**
 * Query keys for contents (unified content model)
 */
export const contentKeys = {
  /** Base key for all content queries */
  all: ["contents"] as const,

  /** Key for content lists with optional filters */
  lists: () => [...contentKeys.all, "list"] as const,
  list: (filters?: ContentFilters) =>
    [...contentKeys.lists(), filters] as const,

  /** Key for single content details */
  details: () => [...contentKeys.all, "detail"] as const,
  detail: (id: string | number) => [...contentKeys.details(), String(id)] as const,

  /** Key for content with its summary */
  withSummary: (id: string | number) =>
    [...contentKeys.detail(id), "with-summary"] as const,

  /** Key for content statistics */
  stats: () => [...contentKeys.all, "stats"] as const,

  /** Key for content duplicates */
  duplicates: (id: string | number) =>
    [...contentKeys.detail(id), "duplicates"] as const,
}

/**
 * Query keys for summaries
 */
export const summaryKeys = {
  /** Base key for all summary queries */
  all: ["summaries"] as const,

  /** Key for summary lists */
  lists: () => [...summaryKeys.all, "list"] as const,
  list: (filters?: SummaryFilters) =>
    [...summaryKeys.lists(), filters] as const,

  /** Key for single summary details */
  details: () => [...summaryKeys.all, "detail"] as const,
  detail: (id: string) => [...summaryKeys.details(), id] as const,

  /** Key for summary by content ID */
  byContent: (contentId: string) =>
    [...summaryKeys.all, "by-content", contentId] as const,
}

/**
 * Query keys for themes
 */
export const themeKeys = {
  /** Base key for all theme queries */
  all: ["themes"] as const,

  /** Key for theme analysis lists */
  lists: () => [...themeKeys.all, "list"] as const,
  list: (limit?: number) => [...themeKeys.lists(), { limit }] as const,

  /** Key for single theme analysis */
  details: () => [...themeKeys.all, "detail"] as const,
  detail: (id: string) => [...themeKeys.details(), id] as const,

  /** Key for analysis status */
  analysis: (id: number) => [...themeKeys.all, "analysis", id] as const,

  /** Key for latest analysis */
  latest: [...["themes"], "latest"] as const,

  /** Key for theme graph data */
  graph: (id: string) => [...themeKeys.detail(id), "graph"] as const,

  /** Key for entities list */
  entities: () => [...themeKeys.all, "entities"] as const,

  /** Key for relationships list */
  relationships: () => [...themeKeys.all, "relationships"] as const,
}

/**
 * Query keys for digests
 */
export const digestKeys = {
  /** Base key for all digest queries */
  all: ["digests"] as const,

  /** Key for digest lists */
  lists: () => [...digestKeys.all, "list"] as const,
  list: (filters?: DigestFilters) => [...digestKeys.lists(), filters] as const,

  /** Key for single digest details */
  details: () => [...digestKeys.all, "detail"] as const,
  detail: (id: string) => [...digestKeys.details(), id] as const,

  /** Key for digest revision history */
  history: (id: string) => [...digestKeys.detail(id), "history"] as const,

  /** Key for pending review digests */
  pendingReview: () => [...digestKeys.all, "pending-review"] as const,

  /** Key for digest statistics */
  statistics: () => [...digestKeys.all, "statistics"] as const,
}

/**
 * Query keys for scripts
 */
export const scriptKeys = {
  /** Base key for all script queries */
  all: ["scripts"] as const,

  /** Key for script lists */
  lists: () => [...scriptKeys.all, "list"] as const,
  list: (filters?: { status?: string; digest_id?: number; limit?: number }) =>
    [...scriptKeys.lists(), filters] as const,

  /** Key for single script details */
  details: () => [...scriptKeys.all, "detail"] as const,
  detail: (id: string) => [...scriptKeys.details(), id] as const,

  /** Key for script section */
  section: (scriptId: string, sectionIndex: number) =>
    [...scriptKeys.detail(scriptId), "section", sectionIndex] as const,

  /** Key for pending review scripts */
  pendingReview: () => [...scriptKeys.all, "pending-review"] as const,

  /** Key for approved scripts */
  approved: () => [...scriptKeys.all, "approved"] as const,

  /** Key for review statistics */
  statistics: () => [...scriptKeys.all, "statistics"] as const,
}

/**
 * Query keys for podcasts
 */
export const podcastKeys = {
  /** Base key for all podcast queries */
  all: ["podcasts"] as const,

  /** Key for podcast lists */
  lists: () => [...podcastKeys.all, "list"] as const,
  list: (filters?: { status?: string; limit?: number; offset?: number }) =>
    [...podcastKeys.lists(), filters] as const,

  /** Key for single podcast details */
  details: () => [...podcastKeys.all, "detail"] as const,
  detail: (id: string) => [...podcastKeys.details(), id] as const,

  /** Key for podcast by script ID */
  byScript: (scriptId: string) =>
    [...podcastKeys.all, "by-script", scriptId] as const,

  /** Key for podcast statistics */
  statistics: () => [...podcastKeys.all, "statistics"] as const,

  /** Key for approved scripts ready for audio */
  approvedScripts: () => [...podcastKeys.all, "approved-scripts"] as const,
}

/**
 * Query keys for chat/conversations
 */
export const chatKeys = {
  /** Base key for all chat queries */
  all: ["chat"] as const,

  /** Key for conversation lists */
  conversations: () => [...chatKeys.all, "conversations"] as const,
  conversationList: (artifactType?: string, artifactId?: string) =>
    [...chatKeys.conversations(), { artifactType, artifactId }] as const,

  /** Key for single conversation */
  conversation: (id: string) =>
    [...chatKeys.conversations(), id] as const,

  /** Key for chat configuration */
  config: () => [...chatKeys.all, "config"] as const,
}

/**
 * Query keys for audio digests
 */
export const audioDigestKeys = {
  /** Base key for all audio digest queries */
  all: ["audio-digests"] as const,

  /** Key for audio digest lists */
  lists: () => [...audioDigestKeys.all, "list"] as const,
  list: (filters?: AudioDigestFilters) =>
    [...audioDigestKeys.lists(), filters] as const,

  /** Key for single audio digest details */
  details: () => [...audioDigestKeys.all, "detail"] as const,
  detail: (id: string) => [...audioDigestKeys.details(), id] as const,

  /** Key for audio digests by digest ID */
  byDigest: (digestId: string) =>
    [...audioDigestKeys.all, "by-digest", digestId] as const,

  /** Key for audio digest statistics */
  statistics: () => [...audioDigestKeys.all, "statistics"] as const,

  /** Key for available digests (for generation) */
  availableDigests: () => [...audioDigestKeys.all, "available-digests"] as const,
}

/**
 * Query keys for system/config
 */
export const systemKeys = {
  /** Base key for all system queries */
  all: ["system"] as const,

  /** Key for health check */
  health: () => [...systemKeys.all, "health"] as const,

  /** Key for configuration */
  config: () => [...systemKeys.all, "config"] as const,

  /** Key for available models */
  models: () => [...systemKeys.all, "models"] as const,
}

/**
 * Query keys for prompts (settings)
 */
export const promptKeys = {
  /** Base key for all prompt queries */
  all: ["prompts"] as const,

  /** Key for prompt list */
  lists: () => [...promptKeys.all, "list"] as const,

  /** Key for single prompt detail */
  details: () => [...promptKeys.all, "detail"] as const,
  detail: (key: string) => [...promptKeys.details(), key] as const,
}

/**
 * Combined query keys export
 *
 * Use this for easy access to all query key factories.
 */
export const queryKeys = {
  contents: contentKeys,
  summaries: summaryKeys,
  themes: themeKeys,
  digests: digestKeys,
  scripts: scriptKeys,
  podcasts: podcastKeys,
  audioDigests: audioDigestKeys,
  chat: chatKeys,
  system: systemKeys,
  prompts: promptKeys,
}
