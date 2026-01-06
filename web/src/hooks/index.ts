/**
 * Hooks Module Exports
 *
 * Central export point for all custom hooks.
 */

// Newsletter hooks
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
  useApprovedScripts,
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
