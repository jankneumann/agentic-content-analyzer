/**
 * Hooks Module Exports
 *
 * Central export point for all custom hooks.
 */

/**
 * Newsletter hooks
 * @deprecated Use Content hooks from './use-contents' instead.
 * These hooks will be removed in Phase 4 of Newsletter deprecation.
 */
export {
  useNewsletters,
  useNewsletter,
  useNewsletterWithSummary,
  useNewsletterStats,
  useIngestNewsletters,
  useDeleteNewsletter,
  usePrefetchNewsletters,
  usePrefetchNewsletter,
} from "./use-newsletters"

// Summary hooks
export {
  useSummaries,
  useSummary,
  useSummaryByNewsletter,
  useSummaryStats,
  useTriggerSummarization,
  useRegenerateSummary,
  useDeleteSummary,
} from "./use-summaries"

// Script hooks
export {
  useScripts,
  usePendingScripts,
  useScriptStats,
  useScript,
  useGenerateScript,
  useApproveScript,
  useRejectScript,
  useSubmitScriptReview,
  useReviseScriptSection,
} from "./use-scripts"

// Digest hooks
export {
  useDigests,
  useDigestStats,
  useDigest,
  useDigestSection,
  useGenerateDigest,
  useSubmitDigestReview,
  useApproveDigest,
  useRejectDigest,
  useReviseDigestSection,
} from "./use-digests"

// Podcast hooks
export {
  usePodcasts,
  usePodcastStats,
  usePodcast,
  useApprovedScripts,
  useGenerateAudio,
} from "./use-podcasts"

// Theme hooks
export {
  useAnalyzeThemes,
  useAnalysisStatus,
  useLatestAnalysis,
  useAnalysesList,
} from "./use-themes"

// Chat hooks
export {
  useChatConfig,
  useConversations,
  useConversation,
  useConversationsForArtifact,
  useCreateConversation,
  useDeleteConversation,
  useSendMessage,
  useRegenerateMessage,
  useApplySuggestedAction,
  useChatSession,
} from "./use-chat"
