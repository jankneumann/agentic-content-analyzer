# Plan Findings: add-gemini-batch-processing

## Iteration 1 — current-code replan

### Resolved critical/high findings

1. The original pilot targeted `content_filter.py`, but persisted filter fields
   belong to `IngestionFilterService`; deferring its borderline decision can race
   summarization. Production call-site rollout moved to `batch-ingestion-filter`.
2. Caption and YouTube Gemini calls occur before `Content` persistence and need
   persist-first/resume semantics. They moved to `batch-youtube-processing`.
3. `Content.id` is integer, not UUID. Persistence now specifies a typed integer FK.
4. `youtube_rss_processing` names native-video processing; there is no transcript
   LLM path to branch. The invalid Phase 2 task was removed.
5. Explicit pipeline receipt IDs mean next-day reconciliation is not automatically
   summarized. The unsupported next-morning claim was removed.
6. Gemini batch creation is non-idempotent; the design now defines claim states,
   the provider/DB orphan window, metadata correlation, cancellation, partial
   output, duplicate-poll idempotency, and bounded fallback.
7. Inline and file-mode result mechanics differ. Phase 0 now implements only
   conservatively bounded metadata-keyed inline batches; file mode is deferred.
8. The ROI numbers were not reproducible from current code. The proposal removes
   them and requires cost reports to expose counts and assumptions.
9. Missing CLI/routing/settings spec deltas and work-package decomposition were added.
10. Free-form batch queue jobs would not project to canonical operations. The
    replan uses a PostgreSQL-advisory-lock worker maintenance tick and keeps the
    CLI read-only.

### Accepted constraints

- No production call site is enabled in this change; all modes remain `sync` and
  the global switch remains false.
- Crash-after-provider-acceptance can orphan a provider job because Google batch
  creation has no idempotency key. The system prevents concurrent local claims,
  applies results idempotently, and documents the residual orphan window.
