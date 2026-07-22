# Follow-ups: add-gemini-batch-processing

Deferred work identified while implementing the inert Gemini batch core. These
were originally recorded in `.beads/issues.jsonl`; that tracker was retired on
2026-05-09 (`718726c6`) and briefly reappeared on `agent/update-agent-skills`
before being removed again. The records are preserved here so they survive the
removal and remain discoverable from the change they belong to.

Re-file these against the coordinator (`mcp__coordination__issue_*`) once it is
reachable again — as of 2026-07-22 it fails with `No module named
'rich.traceback'`.

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
per step, and no production call site opts in. Both follow-ups above, and the
submission-failure classification in `src/services/batch/workers.py`, must be
settled before any step is switched on.
