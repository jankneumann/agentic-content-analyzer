/**
 * Hooks Module Exports
 *
 * Central export point for all custom hooks.
 */

// Summary hooks
export {
  useSummaries,
  useSummary,
  useSummaryByContent,
  useSummaryByNewsletter, // deprecated, use useSummaryByContent
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

// Content hooks (unified content model)
export {
  useContents,
  useContent,
  useContentWithSummary,
  useContentStats,
  useContentDuplicates,
  useCreateContent,
  useIngestContents,
  useDeleteContent,
  useMergeContentDuplicate,
  usePrefetchContents,
  usePrefetchContent,
  useSummarizeContents,
} from "./use-contents"
