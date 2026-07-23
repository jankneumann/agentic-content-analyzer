# Follow-ups: add-gemini-batch-processing

Deferred work identified while implementing the inert Gemini batch core. These
were originally recorded in `.beads/issues.jsonl`; that tracker was retired on
2026-05-09 (`718726c6`) and briefly reappeared on `agent/update-agent-skills`
before being removed again. The records are preserved here so they survive the
removal and remain discoverable from the change they belong to.

**Migrated to GitHub Issues on 2026-07-22** — these are now tracked live:
- `…-0vd` → [#464](https://github.com/jankneumann/agentic-content-analyzer/issues/464)
- `…-6bc` → [#465](https://github.com/jankneumann/agentic-content-analyzer/issues/465)

The beads DB held nothing else open, so it was deleted after this migration. The
detail below is retained for historical context.

## Open

### Batch the post-persist ingestion filter safely

- **Legacy id**: `agentic-newsletter-aggregator-0vd`
- **Type**: feature
- **Priority**: 2

Batch only the borderline `IngestionFilterService` LLM tier, with explicit
pipeline gating, status restore / filter-out semantics, and resume behavior.

The original proposal assumed call sites could enqueue and return. They cannot
today: ingestion filtering gates the same pipeline run, so a naive enqueue
strands the run. This follow-up covers the gating work that unblocks it.

### Add persist-first YouTube and caption batch processing

- **Legacy id**: `agentic-newsletter-aggregator-6bc`
- **Type**: feature
- **Priority**: 3

Introduce durable pre-persist staging for YouTube native-video and caption
proofreading, plus ready-for-summarization backlog and resume behavior.

Caption and native-video outputs are currently consumed before a `Content` row
exists, so there is nothing durable to attach a batch result to. This follow-up
covers the persist-first restructuring that makes batching those paths safe.

## Prerequisite before enabling any batch step

Batch execution ships inert: `batch_execution` defaults to disabled globally and
per step, and no production call site opts in. Both follow-ups above must be
settled before any step is switched on.

Submission-failure classification was settled in `a780e1e7`: permanent
`ValueError` rejections route to the bounded sync fallback instead of requeueing
forever. Two residual sharp edges are worth closing before enabling a step —
the permanent/retryable split keys off `ValueError` rather than a dedicated
exception type, and a permanently unset `GOOGLE_API_KEY` still accumulates one
failed job row per sweep because credential errors are deliberately retryable.
