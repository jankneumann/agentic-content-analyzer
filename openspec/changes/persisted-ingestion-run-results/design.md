# Design: Operation-native ingestion history

## Context

The original July ingestion-reliability plan proposed `IngestionRun` and
`SourceRunResult` tables because pipeline drivers discarded partial results.
That premise changed when canonical durable workflows shipped:
`pgqueuer_jobs` now owns operation lifecycle, parent-child relationships,
checkpoints, retries, idempotency, typed resources, results, and problems.

The remaining loss occurs at projection boundaries. `IngestionResponse`
contains three-state source status and counts, but `IngestionResult` drops
status, skipped/failed counts, and errors. `OperationService.list()` returns
unfiltered full handles. The existing 30-day cleanup helper has no production
caller and is row-local rather than graph-aware.

## Decisions

### D1: `pgqueuer_jobs` remains the only workflow authority

No run/source-result table is introduced. The stored operation result is
enriched additively, and history is a read projection. A future materialized
read model requires measured JSONB query failure or a history window longer
than queue retention.

### D2: Source outcome is distinct from operation lifecycle

The shared classifier exposes:

- `success` — completed with positive items and no source failure;
- `zero_items` — completed with zero items and no failure;
- `partial` — some work succeeded while a source/item failure survived;
- `failed` — operation failed or the source-domain result is an error;
- `cancelled` — operation lifecycle is cancelled;
- `unknown` — legacy rows lack enough data for a truthful classification.

`unknown` is mandatory for old completed rows because the dropped partial
signal cannot be reconstructed.

Pipeline aggregation is deterministic:

| Pipeline lifecycle | Child outcomes | Aggregate outcome |
|---|---|---|
| `cancelled` | any | `cancelled` |
| `failed` | any | `failed` |
| `completed` | any `partial`, `failed`, or `cancelled` | `partial` |
| `completed` | otherwise any `unknown` | `unknown` |
| `completed` | no children or all `zero_items` | `zero_items` |
| `completed` | `success` plus optional `zero_items` | `success` |

The lifecycle rows take precedence because strict partial/failure policy can
fail the parent even when some child work succeeded.

### D3: Typed results retain exact provenance once, bounded diagnostics elsewhere

The current shape remains `IngestionResultV1`; writers emit strict
`IngestionResultV2`; readers accept their union. V2 preserves canonical
status/counts. Exact `content_ids` remain because the pipeline consumes them as
provenance, but they appear once rather than again inside `details`.

One sanitizer owns deterministic ordering, safe-code validation, URL/query/key
redaction, control-character removal, maximum message length, separate
error/warning omitted counts, a global diagnostic count, bounded source
outcomes, and a 64 KiB serialized metadata budget excluding the exact
content-ID array. V2 command details use an explicit numeric/boolean allowlist;
prompt/query/citation/URL/identifier and arbitrary nested values are omitted.
This prevents per-source caps from multiplying into a nominally bounded but
megabyte-sized handle.

Configured-source public keys are derived once at the configuration boundary
with HMAC-SHA256 and a dedicated durable `CONFIGURED_SOURCE_KEY_SECRET`.
Production/staging startup fails when it is missing; test environments may
inject a fixed test-only value. Authentication-secret fallback is forbidden.
Rotation requires an explicit dual-key migration/backfill change because
silently replacing the key would make retained 30/90-day history unqueryable.
Aggregators carry the public key and never rederive identity from an error URL,
redirect, prompt, or mailbox query.

### D4: Tolerated partial pipelines warn rather than fail

`continue_on_source_error=true` is an explicit request to finish downstream
work. A completed partial pipeline therefore remains exit 0 but prints a
warning on stderr; JSON exposes `result.ingestion_summary.outcome=partial`.
With continuation disabled, either a failed or partial source fails the
pipeline and the waiting CLI exits 1. A zero-item source is not a source error:
it stays exit 0 and receives an informational human summary.

### D5: Dedicated compact ingestion history preserves compatibility

`GET /api/v1/ingestions` is added alongside the existing POST at the same
canonical collection. It returns terminal operations only as
`IngestionHistoryPage`, not `OperationPage`. `aca ingest history` mirrors the
filters.

Rows include identity, command, bounded opaque configured-source summaries,
lifecycle status, outcome, counts, optional parent, retry count, problem code,
status URL, and timestamps. Filters distinguish the command key from an opaque
configured-source key. Rows exclude input, result/checkpoint bodies,
diagnostics text, resolved sets, and content IDs.

The API caps each page at 100 rows. CLI `--all` traversal is guarded by
`--max-pages` (default 20, maximum 100), so one command cannot create an
unbounded request burst. On budget exhaustion JSON returns one
`{data,next_cursor,truncated:true}` document and human output prints a warning
with the continuation cursor. Generic operation traversal receives the same
budget. The web Background Tasks indicator fetches one recent page plus bounded
`queued` and `in_progress` pages rather than hydrating the entire retention
window. Existing API authentication and deployment rate controls continue to
apply. The current deployment is owner-wide; a future multi-tenant mode must
add ownership predicates before exposing this query.

The GET inherits the same authentication and authorization middleware as the
existing POST collection and operation endpoints. Adding history MUST NOT
create an anonymous or differently authorized read path.

Generic `GET /api/v1/operations` becomes summary-only: its rows omit result,
checkpoint/input, resource metadata, and problem detail while retaining only
the existing required `OperationHandle` wire keys plus timestamps. No new row
key is introduced, so old strict generated clients accept the summary as a
valid handle with optional result/resource/problem absent. First-party
API/CLI/web list consumers use `OperationSummary`;
exact `GET /api/v1/operations/{id}` remains the sole full-result read. This is
a wire-compatible response narrowing at the list boundary, with
generated-model and consumer migration in the same change.

### D6: Keyset cursors are signed and bound to normalized filters

History ordering is `(created_at DESC, id DESC)`. A size-limited versioned
cursor carries that position plus the normalized filters and is signed with
HMAC-SHA256 using `OPERATION_CURSOR_SIGNING_KEY`, falling back to an existing
application/admin secret. Signatures are compared in constant time. Missing
signing material fails closed. Replaying a cursor with different filters,
tampering, oversize decoded data, an invalid bigint, or an invalid time window
is rejected. UTC-equivalent timestamps normalize identically and the window
is half-open: `created_after <= created_at < created_before`.

Task 4.7 measures representative 10,000-row query plans before adding only the
smallest demonstrated ordering or JSONB-expression indexes. The plan gate uses
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` and asserts bounded rows scanned for
selective filters rather than trusting a tiny fixture.

### D7: Retention is graph-aware worker maintenance

The existing `job_retention_days`/`JOB_RETENTION_DAYS` setting remains the
completed/cancelled horizon and defaults to the documented 30 days.
`failed_job_retention_days`/`FAILED_JOB_RETENTION_DAYS` defaults to 90 and
cannot be shorter than the completed horizon. Both horizons are bounded to
1–3650 days; zero does not silently disable cleanup. Validated
`JOB_RETENTION_INTERVAL_SECONDS` and `JOB_RETENTION_BATCH_SIZE` settings
control work volume. Worker maintenance is independent of optional Gemini
batch maintenance. It runs at startup plus a process-local interval, takes a
PostgreSQL advisory lock with bounded lock/statement timeouts, and removes a
bounded batch of eligible root graphs while emitting count/duration metrics.
Duplicate runs after restarts are safe and idempotent; the lock promises
single concurrency, not exactly-once scheduling.

A graph is eligible only when every node is terminal, no node has a null
completion time, and `MAX(completed_at) < cutoff`. SQL checks the null count
explicitly because `MAX` alone would ignore nulls. Graphs containing failed
nodes use the longer failed cutoff; completed/cancelled-only graphs use the
normal cutoff. Queued or in-progress nodes always preserve the graph.
Candidates are rechecked under transactional row locks immediately before
descendants are deleted.

The implementation uses one transaction and deletes descendants before roots;
no surviving row is detached through `ON DELETE SET NULL`.

## Data Flow

```text
IngestionService
  -> IngestionResponse(status, counts, source_outcomes, diagnostics)
  -> workflow handler
  -> typed IngestionResult in pgqueuer_jobs.payload.result
  -> PipelineWorkflow source summary + shared outcome classifier
  -> compact GET /api/v1/ingestions projection
  -> WorkflowApiClient
  -> aca ingest history / pipeline wait warning
```

## Contract Evolution

The domain-history additions are additive. One deliberate compatibility
narrowing removes full payloads from generic operation list rows:

- the persisted ingestion result carries its own result schema version;
- the existing POST `/api/v1/ingestions` is unchanged;
- GET `/api/v1/ingestions` is new;
- exact `OperationHandle.result` remains available for cross-operation
  compatibility;
- `OperationPage.data` becomes `OperationSummary[]`, and first-party consumers
  migrate atomically; emitted rows remain a key-compatible subset of the
  existing strict `OperationHandle`;
- generated Python and TypeScript models gain the typed result, summary, and
  history models.

## Security and Privacy

- Configured-source natural keys include URLs, IDs, prompts, and queries.
  Public identity uses `src_<20 hex HMAC prefix>` with a dedicated stable
  secret, preventing offline tests of low-entropy locators.
- History pages expose counts and diagnostic codes, not diagnostic messages.
- Command-specific `details` are reduced to a closed numeric/boolean property
  allowlist with explicit omitted counts; arbitrary adapter output is not
  copied into the durable public result.
- Exact operation GET retains bounded messages for diagnosis and remains under
  existing API authorization.
- Generic operation lists expose summaries only and have no result/provenance
  opt-in.
- Cursor contents are opaque and reveal no locator or raw filter values beyond
  those already present in the request.
- Signing keys are secret settings, never cursor payload fields or log values.

## Alternatives Rejected

- **Immutable terminal read-model table:** useful only after a measured query or
  retention gap; otherwise it creates a dual-write reconciliation problem.
- **Authoritative run/source tables:** duplicates the operation state machine.
- **Leaving `OperationPage` as full handles:** enriched results would multiply
  sensitive provenance across list pages. The bounded migration is preferable
  to preserving that exposure.
- **Inferring legacy success:** produces false green history for partial runs.
- **Deleting failed rows after the same 30-day window:** removes retryable work
  and its checkpoint too quickly. A separate 90-day default gives operators a
  finite retry horizon while preventing indefinite storage growth.
- **Using raw configured-source locators:** leaks private URLs, prompts, and
  mailbox queries into history.

## Task Sizing

The L-sized change is split across contract/result, pipeline classification,
history, and retention packages. Each implementation task is S or M. No task
is XL and no individual task owns both a new authority and a query surface.
