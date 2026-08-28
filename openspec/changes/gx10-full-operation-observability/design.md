## Context

The backend combines FastAPI, PostgreSQL-backed durable operations, multiple worker entrypoints, scheduled and maintenance work, ingestion adapters, parsers, model providers, PostgreSQL persistence, Neo4j/Graphiti, storage, indexing, delivery, structured logs, OpenTelemetry, and Langfuse. Those pieces already emit useful evidence, but no attempt-aware contract joins them.

Today an HTTP trace ends when a job is submitted because W3C context is not stored in the queue row. A worker creates unrelated telemetry, exact OperationHandle reads have no durable trace locator, the CLI worker can initialize without telemetry, and the local profile can enable OTel without configuring an exporter. YouTube catches some item exceptions and returns false, which the aggregator can report as a successful skip; blog failures preserve only inconsistent short messages. The existing PostgreSQL job graph must remain the workflow source of truth.

The target is a production GX-10 with a 1 TB local disk. All internal services move local; approved model and content APIs remain external. Detailed evidence belongs in self-hosted Langfuse, while PostgreSQL stores the safe minimum required to navigate attempts after restarts and to diagnose trace-delivery loss.

## Goals / Non-Goals

### Goals

- Resolve any durable operation ID to its root operation, every claim attempt, service/release, terminal stage/outcome, trace ID, and detailed Langfuse evidence.
- Cover all meaningful work, not only LLM and pipeline decorators.
- Preserve batch continuation while making per-item ingestion failures truthful.
- Keep rich stacks, timings, fallback decisions, and bounded redacted excerpts in Langfuse.
- Keep PostgreSQL authoritative and bounded, with no duplicate workflow state machine.
- Operate the complete internal stack on the GX-10 with production secrets, persistence, health, backups, retention, disk alarms, and rollback fencing.
- Ship additive contracts that read legacy operations safely during coexistence.

### Non-Goals

- Moving Railway data or switching production traffic in this change.
- Replacing PostgreSQL queue semantics, Graphiti, Neo4j, Langfuse, or OpenTelemetry.
- Storing full prompts, articles, transcripts, raw URLs, or stacks in PostgreSQL.
- Forking or directly mutating Langfuse-owned PostgreSQL or ClickHouse schemas.
- Air-gapping the GX-10 from approved external providers.
- Building a general-purpose metrics warehouse or log-search product.

## Decisions

### D1. One versioned OperationContext envelope

Create a typed, immutable context envelope in the telemetry/domain boundary. Version 1 carries operation, root/parent, W3C trace, attempt/claim, entrypoint, service instance, environment, release, stage, and opaque resource identity. Values have fixed bounds and validators. Context enters process-local context variables only after validation.

External W3C context is accepted at trusted protocol boundaries, but ACA operation fields are created or resolved server-side. Invalid external context is discarded and reported by code, never reflected.

Why: one contract prevents each adapter from inventing correlation fields and makes logs, PostgreSQL, OTel, and Langfuse converge.

### D2. Continue one trace and separate every claim attempt

Submission creates or continues a trace and stores its W3C carrier before the job is visible. Each successful claim creates an attempt root span beneath that carrier; claim generation is the attempt fencing key. Child durable operations receive new operation IDs but keep root and parent operation IDs and continue the active trace.

Queue wait is represented from submitted-at to claimed-at without leaving a live in-memory span. Retries append attempt evidence; they never overwrite earlier attempts.

Why: this preserves a navigable trace while making failures, retries, stale claims, and restarts explicit.

### D3. PostgreSQL stores correlation, not telemetry payloads

Add nullable correlation columns to pgqueuer_jobs and a normalized operation_observation_attempts projection keyed by operation ID plus claim generation. The queue row owns current/root correlation; the attempt table owns immutable-per-attempt start identity and bounded mutable completion evidence.

Attempt fields are limited to identifiers, timestamps, service/release, stage/outcome/error codes, retryability, telemetry-delivery state, and omitted-detail counters. PostgreSQL constraints validate hex widths and enumerations; indexes support operation, root operation, trace, and terminal-failure queries.

The attempt projection is not a workflow state machine: it cannot enqueue, claim, cancel, retry, or determine canonical operation status.

Why: an operation remains diagnosable when telemetry export fails without duplicating Langfuse.

### D4. Shared stage and outcome vocabulary

Use generated enums from the event contract. Stable stages include submit, queue_wait, claim, fetch, discover, metadata, transcript, extract, parse, filter, deduplicate, model, fallback, persist, index, graph, deliver, backup, restore, alert, cleanup, and flush. Adapters may add a bounded substage but cannot add unreviewed top-level stages.

Outcomes are succeeded, partial, skipped_policy, skipped_duplicate, filtered, retryable_failure, permanent_failure, and cancelled. Error class and diagnostic code are separate. A caught exception must become retryable_failure or permanent_failure unless a documented domain rule identifies a non-error.

Why: dashboards and SQL diagnostics need stable values, while code/message detail remains implementation-specific.

### D5. Langfuse receives rich controlled OTel-native detail

Use the current supported Langfuse/OpenTelemetry ingestion path and keep SDK versions compatible with the deployed Langfuse version. Domain operations use descriptive spans; LLM calls use generation observations with model, tokens, latency, cost, prompt version when safe, and provider response metadata. Database/graph lookups use suitable span or retriever observations; writes remain spans.

Instrumentation explicitly sets bounded inputs and outputs. Automatic arbitrary-argument capture is disabled. A shared export-time masker covers Langfuse-native and third-party OTel spans, removing secrets, auth data, sensitive query parameters, PII canaries, and disallowed content. Full exception stacks are allowed only after masking and only in Langfuse.

Production starts at 100 percent meaningful-operation trace coverage. Sampling may be introduced only after measured volume tests and must preserve failures and durable evidence.

Why: the current Langfuse SDK is OTel-native and export-time masking covers third-party spans more reliably than decorator-only sanitization.

### D6. Telemetry degradation is explicit but not domain state

A shared lifecycle initializes configuration and telemetry before instrumented clients for API, deployment worker, CLI worker, scheduler, agent, backup, and maintenance entrypoints. It exposes initialized state, exporter endpoint class, last success/error age, buffered/dropped counts, and flush result.

Required-observability production profiles fail activation for missing configuration and degrade readiness for sustained delivery failure. Domain operations continue or stop according to their own safety policy; an exporter outage never rewrites workflow outcome.

Why: visibility must not fail silently, but telemetry availability must not create a second business-state authority.

### D7. Exact-operation diagnostics are additive and authorized

Extend the exact OperationHandle with an optional observability object and add an admin-only attempt endpoint. Collection rows keep at most trace ID plus bounded codes. The server constructs Langfuse lookup URLs from trusted base configuration and opaque trace IDs; clients never provide destinations.

Audit rows persist real trace/span IDs separately from request ID. Terminal events retain operation ID, claim generation, and trace ID. SSE snapshots may include bounded correlation but never detailed stacks or excerpts.

Why: operators need one-click navigation while list APIs remain safe and inexpensive.

### D8. GX-10 is a production topology, not a development Compose file

Create a production overlay/profile with pinned images, non-default secrets, private service networks, persistent named/bind volumes, dependency health checks, restart/backoff policy, CPU/memory reservations, and distinct API/worker/scheduler/maintenance service names. Only authenticated TLS ingress and explicitly approved operator surfaces leave the host.

The deployment validates stateful port exposure and keeps approved external HTTPS egress for model, transcription, feed, page, video, email, and notification providers.

Why: the existing Langfuse Compose is development-grade and the local profile does not fully activate infrastructure telemetry.

### D9. Disk policy reserves failure evidence and host headroom

Initial logical budgets on a 1 TB disk are: application PostgreSQL 22 percent, Neo4j 12 percent, ClickHouse 28 percent, MinIO 8 percent, backups 15 percent, Redis/local logs 2 percent, and at least 13 percent reserve. Operators may lower component budgets, but configured maxima plus reserve cannot exceed the managed filesystem.

High and critical watermarks default to 80 and 90 percent. At high watermark, reduce concurrency/detail and run supported cleanup. At critical, pause nonessential ingestion and alert. Never remove database files from the filesystem.

Target retention is 30 days for successful/partial detailed traces and 90 days for failed detailed traces and failed PostgreSQL attempt evidence. Native Langfuse retention is capability-detected. When outcome-specific supported deletion is unavailable, retain all traces up to 90 days and make the increased usage visible. No direct Langfuse schema changes are allowed.

Why: failure evidence is most valuable, but a storage-saving policy must not corrupt ClickHouse or MinIO.

### D10. Backups and restores are first-class operations

Scheduled backups create durable maintenance operations and component stage spans for application PostgreSQL, Neo4j, Langfuse PostgreSQL, ClickHouse, MinIO, and non-secret configuration. Artifacts are encrypted where available, checksummed, quota-accounted, and retained by policy. Restore drills target isolated volumes and validate application operation rows plus Langfuse trace metadata.

Why: observability that disappears during host recovery is not production observability.

### D11. Environment ownership uses a fence

GX-10 and Railway may coexist during rollout, but a stored environment ownership epoch gates schedulers and mutation claims. Only the active environment may schedule ingestion or claim mutation work. Every trace records environment and release. Rollback first fences GX-10, then validates the passive target, then enables target mutations.

Why: DNS or configuration toggles alone cannot prevent duplicate scheduled work.

### D12. Contract-first TDD and staged rollout

Freeze OpenAPI, SQL, and event schemas before implementation. Implement failing tests before each behavior package. Roll out in stages: schema/read compatibility, shared context and propagation, adapter classification, operator APIs, GX-10 topology, then full smoke/restore validation. A feature flag allows correlation writes and detailed trace export to be enabled independently while reads remain backward-compatible.

Why: the central queue and operation modules are highly coupled; a frozen contract and serial core reduce integration risk while adapters and deployment can proceed in parallel afterward.

## Data Flow

1. An ingress creates or validates W3C context and allocates a durable operation.
2. Submission writes the operation graph and trace carrier atomically before queue visibility.
3. A claim increments claim generation and starts the attempt projection/span.
4. Context variables enrich logs, Langfuse/OTel observations, child submissions, and bounded PostgreSQL evidence.
5. Stage helpers classify each outcome; caught exceptions emit masked detailed evidence and safe codes.
6. Attempt completion is fenced by claim generation, then the canonical operation completes through existing job semantics.
7. Exact reads join operation state to bounded attempts and generate an authorized Langfuse lookup link.
8. Retention and backup jobs operate as correlated maintenance operations.

## Risks / Trade-offs

- **Long-lived traces:** scheduled/queued work can span long intervals. Mitigation: queue wait is reconstructed from timestamps, not held as a live span.
- **Context cardinality:** trace and operation IDs are high-cardinality. Mitigation: use them for logs/traces and indexed exact queries, never metric labels.
- **Trace volume:** 100 percent coverage can fill disk. Mitigation: strict excerpts, budgets, watermarks, measured sizing, and capability-aware retention before sampling.
- **Failure-biased sampling limitations:** head sampling cannot know terminal outcome. Mitigation: begin unsampled; any future policy requires tail-capable preservation or deterministic re-export design.
- **Exporter outage:** Langfuse detail can be delayed or lost. Mitigation: bounded attempt evidence and exporter health in PostgreSQL/readiness.
- **Schema coupling:** queue changes touch hot files. Mitigation: additive nullable migration, legacy-read tests, contract-first serialization, and a serialized core package.
- **Langfuse version drift:** SDK/API behavior changes. Mitigation: pinned compatible versions, official OTel ingestion, capability detection, and no internal schema edits.
- **Sensitive exceptions:** stacks can include payload fragments. Mitigation: export-time masking plus canary tests before acceptance.
- **Dual-environment mutation:** coexistence can duplicate work. Mitigation: stored ownership epoch and claim-time fence.

## Migration Plan

1. Add nullable queue correlation columns, attempt projection, constraints, and indexes; deploy readers that tolerate nulls.
2. Deploy the shared vocabulary, context serializer, masker, and telemetry lifecycle behind disabled write/export flags.
3. Enable submission propagation, claim extraction, and attempt writes for synthetic operations; verify restart and retry behavior.
4. Enable exact-operation/audit/terminal correlation surfaces.
5. Instrument YouTube and blog failure paths, then remaining adapters and operational entrypoints.
6. Deploy and harden the GX-10 stack with empty/new observability volumes; run capacity, ingress, health, backup, and restore validation.
7. Run backend-neutral trace-arrival/redaction smoke tests and a measured ingestion soak.
8. Enable GX-10 as mutation owner only in the separate cutover change. Preserve Railway as passive rollback until cutover acceptance.

Rollback before cutover disables new correlation writes/exports while additive columns remain readable. Rollback after cutover is owned by the separate data/traffic migration and MUST use the environment fence before enabling Railway mutations.

## Validation Strategy

- Unit tests for envelope validation, context variables, W3C inject/extract, masking, outcome taxonomy, and profile validation.
- Contract tests against OpenAPI, event JSON Schema, and SQL constraints.
- Queue integration tests for submission/claim atomicity, retry generations, stale claims, restarts, child operations, and legacy rows.
- Adapter tests that force YouTube/blog failures and verify truthful counts plus continued batch execution.
- Telemetry tests with an in-memory exporter and local Langfuse verifier for hierarchy, generations, flush, and secret canaries.
- GX-10 tests for health dependency order, restart recovery, private ports, watermarks, retention capability modes, backups, and isolated restore.
- End-to-end synthetic operation joining API response header, PostgreSQL operation/attempt rows, structured logs, and Langfuse trace.

## References

- Langfuse OpenTelemetry compatibility: https://langfuse.com/docs/compatibility
- Langfuse masking: https://langfuse.com/docs/observability/features/masking
- Langfuse data retention: https://langfuse.com/docs/administration/data-retention
- Langfuse self-hosted backups: https://langfuse.com/self-hosting/configuration/backups
- Langfuse self-hosted hardening: https://langfuse.com/self-hosting/configuration/hardening
