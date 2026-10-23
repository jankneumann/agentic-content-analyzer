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
- Building a new frontend observability UI; the existing CLI may consume additive exact-operation fields.
- Activating GX-10 mutation ownership, migrating data, or switching public production traffic before the separate cutover change is approved.

## Decisions

### D1. One versioned OperationContext envelope

Create a typed, immutable context envelope in the telemetry/domain boundary. Version 1 carries operation, root/parent, W3C trace, claim generation, nullable attempt number, entrypoint, service instance, environment, release, stage, and opaque resource identity. All nullable wire keys are required and encoded as explicit null so structural JSON Schema and OpenAPI validation agree on shape and scalar bounds. Schema-version `1` follows JSON numeric equality: lexical `1` and `1.0` are equivalent after standards-compliant parsing, while booleans and strings are rejected. Standard structural schemas cannot express cross-field identity or arithmetic: every ingress and deserializer MUST call the generated composite Python or TypeScript semantic validator before accepting an envelope; raw type assertions and structural-only validation are forbidden. Before a claim, attempt number is null; after a claim, it equals claim generation plus one, matching the existing terminal-alert convention. Operation IDs, epochs, claim generations, attempt numbers, and cursors use the signed 64-bit database range and cross JSON/JavaScript boundaries as canonical decimal strings so values above 2^53-1 remain lossless. Claimed generation is capped at 9223372036854775806, reserving headroom for `attempt_number = claim_generation + 1`; max, max+1, and overflow cases are cross-artifact tests. Values have fixed bounds and validators. Context enters process-local context variables only after validation.

External W3C context is accepted at trusted protocol boundaries, but ACA operation fields are created or resolved server-side. Version-1 validation accepts only canonical W3C version-00 traceparent syntax, rejects all-zero trace and parent identifiers, requires the carrier trace and parent IDs to equal the envelope's explicit trace and span IDs, and validates a bounded W3C tracestate subset. Invalid external context is discarded and reported by code, never reflected.

Why: one contract prevents each adapter from inventing correlation fields and makes logs, PostgreSQL, OTel, and Langfuse converge.

### D2. Continue one trace and separate every claim attempt

Submission creates or continues a trace and stores its W3C carrier before the job is visible. Each successful claim creates an attempt root span beneath that carrier; claim generation is the attempt fencing key. Child durable operations receive new operation IDs but keep root and parent operation IDs and continue the active trace.

Queue wait is represented from submitted-at to claimed-at without leaving a live in-memory span. Retries append attempt evidence; they never overwrite earlier attempts.

Why: this preserves a navigable trace while making failures, retries, stale claims, and restarts explicit.

### D3. PostgreSQL stores correlation, not telemetry payloads

Add nullable correlation columns plus a bounded, versioned context member to pgqueuer_jobs and a normalized operation_observation_attempts projection keyed by operation ID plus claim generation. The queue row owns submission/root correlation; the attempt table owns immutable-per-attempt start identity and bounded mutable completion evidence. Context and operation rows are written in the same transaction before queue visibility. PostgreSQL CHECK constraints require the duplicated indexed row ID, root ID, W3C carrier, trace ID, and submission span ID to equal their canonical `submission_context` values, so lookup and worker continuation cannot diverge.

PostgreSQL retains one summary per claim attempt, not an intermediate-stage ledger. Attempt fields are limited to identifiers, timestamps, service/release, current or terminal stage/outcome/error codes, retryability, telemetry-delivery state, and omitted-detail counters. Detailed stage spans and timings remain in Langfuse. PostgreSQL constraints validate 64-bit claim generations, hex widths, diagnostic string type/pattern/byte bounds, enumerations, and serialized diagnostic size; indexes support operation, root operation, trace, and terminal-failure queries. Cleanup retains root/parent tombstones until the longest-lived child or failed attempt expires, so deleting successful detail cannot break retained correlation.

The attempt projection is not a workflow state machine: it cannot enqueue, claim, cancel, retry, or determine canonical operation status.

Why: an operation remains diagnosable when telemetry export fails without duplicating Langfuse.

### D4. Shared stage and outcome vocabulary

Use generated enums from the event contract. Stable stages include submit, queue_wait, claim, fetch, discover, metadata, transcript, extract, parse, filter, deduplicate, model, fallback, persist, index, graph, deliver, backup, restore, alert, cleanup, and flush. Adapters may add a bounded substage but cannot add unreviewed top-level stages.

Outcomes are succeeded, partial, skipped_policy, skipped_duplicate, filtered, retryable_failure, permanent_failure, and cancelled. Error class and diagnostic code are separate. A caught exception must become retryable_failure or permanent_failure unless a documented domain rule identifies a non-error.

Why: dashboards and SQL diagnostics need stable values, while code/message detail remains implementation-specific.

### D5. Langfuse receives rich controlled OTel-native detail

Use the current supported Langfuse/OpenTelemetry ingestion path and keep SDK versions compatible with the deployed Langfuse version. Domain operations use descriptive spans; LLM calls use generation observations with model, tokens, latency, cost, prompt version when safe, and provider response metadata. Database/graph lookups use suitable span or retriever observations; writes remain spans.

Instrumentation explicitly sets bounded inputs and outputs: each selected excerpt is at most 4 KiB after UTF-8 encoding, each masked exception stack is at most 64 KiB, each span has at most 128 attributes and at most 128 KiB of serialized payload, and each process-local attempt exports at most 256 observations or 16 MiB before provider framing. The attempt helper reserves the final 64 observations and 4 MiB for terminal, failure, security, backup, restore, and telemetry-health evidence. When the success-detail budget is exhausted it drops successful excerpts first, then optional successful model/provider metadata, while preserving root/stage topology and incrementing durable omitted counters. Child operations and retries receive independent enforceable attempt budgets; there is no unenforceable distributed trace-wide byte cap. Automatic arbitrary-argument capture is disabled. A shared export-time masker covers Langfuse-native and third-party OTel spans, removing secrets, auth data, sensitive query parameters, PII canaries, and disallowed content. Full exception stacks are allowed only after masking, truncation, and only in Langfuse. Export buffers are bounded to 10,000 spans or 256 MiB per process; overflow increments durable drop counters and degrades readiness.

Production starts at 100 percent meaningful-operation trace coverage. Sampling may be introduced only after measured volume tests and must preserve failures and durable evidence.

Why: the current Langfuse SDK is OTel-native and export-time masking covers third-party spans more reliably than decorator-only sanitization.

### D6. Telemetry degradation is explicit but not domain state

A shared lifecycle initializes configuration and telemetry before instrumented clients for API, deployment worker, CLI worker, scheduler, agent, backup, and maintenance entrypoints. It exposes initialized state, exporter endpoint class, last success/error age, buffered/dropped counts, and flush result.

Required-observability production profiles fail activation for missing configuration and degrade readiness for sustained delivery failure. Long-running processes heartbeat bounded initialization/export/buffer/drop state to a PostgreSQL process-health projection keyed by environment, service, and instance with freshness expiry; short-lived processes persist their final flush evidence. Each row persists constrained `lifecycle_kind` and `expires_at`: long-running rows expire 24 hours after their last heartbeat and short-lived final-flush rows expire after 7 days. Cleanup deletes expired rows only; queries return the newest 1,000 nonexpired rows per environment plus an omitted count and never delete current rows merely to meet the response cap. The observability health API aggregates those rows and never implies that one API process represents the deployment. Domain operations continue or stop according to their own safety policy; an exporter outage never rewrites workflow outcome. Bootstrap/secret-provisioning commands that run before PostgreSQL is ready write masked, hash-chained, mode-0600 JSONL evidence to `/srv/aca/bootstrap-audit`; the first healthy maintenance process imports and correlates that evidence, and corrupt or missing required spool evidence degrades production readiness.

Why: visibility must not fail silently, but telemetry availability must not create a second business-state authority.

### D7. Exact-operation diagnostics are additive and authorized

Extend the exact OperationHandle with an optional observability object and add an operator-only attempt endpoint. The API/audit package owns the operator setting, distinct secret/role dependency, rotation-safe negative tests, and authorization behavior; the GX-10 runtime package depends on it and wires the OpenBao reference/rotation. A normal authenticated session and the legacy session-compatible admin helper do not grant it. Collection rows keep at most trace ID plus bounded codes. The server constructs Langfuse lookup URLs from trusted base configuration and opaque trace IDs; clients never provide destinations. Existing exact-operation authorization remains compatible, but non-operator callers receive null privileged links and cannot read attempt pages or deployment-wide health.

Audit rows persist real trace/span IDs separately from request ID. Terminal events retain operation ID, claim generation, and trace ID. SSE snapshots may include bounded correlation but never detailed stacks or excerpts.

Why: operators need one-click navigation while list APIs remain safe and inexpensive.

### D8. GX-10 is a production topology, not a development Compose file

Use rootful Podman Compose for service topology, supervised by systemd units for boot order and bounded restart/backoff. Caddy owns authenticated TLS ingress and certificate renewal. OpenBao is the authoritative production secret source; generated protected environment files are runtime-only and mode 0600. Private Compose networks plus host firewall rules deny public stateful ports. Application networks have no direct Internet route: outbound HTTPS passes through a dedicated Squid 6.6 container (`ubuntu/squid:6.6-24.04_beta`, required to be locked by immutable image digest in the rendered deployment) that resolves DNS and enforces `squid.conf` `dstdomain` plus CONNECT-port ACLs; only Squid has outbound access. Proxy credentials come from OpenBao, policy is mounted read-only and reloads only after syntax validation, readiness uses a bounded allowed-host probe, and CONNECT logs retain only masked host/port/status/timing metadata. Explicit DNS, NTP, certificate-bootstrap, and proxy-health exceptions are pinned and tested. Unknown destinations, stale or invalid policy, DNS failure, credential failure, or proxy failure fail closed for external calls while local safety/diagnostic operations remain available. Squid is a required healthy dependency for application services configured with external providers, and direct-route denial is tested from every application network namespace. Distinct API/worker/scheduler/maintenance service identities are mandatory.

State lives under a dedicated `/srv/aca` filesystem. The application storage controller enforces logical component budgets and watermarks using supported service retention APIs; deployment validation fails if the filesystem capacity cannot satisfy the configured budgets and reserve. OS project quotas are optional defense in depth, not a portability prerequisite.

Why: these choices match the repository's Compose, systemd backup, and OpenBao operating patterns while making ingress, supervision, secrets, networks, and storage ownership testable.

### D9. Disk policy reserves failure evidence and host headroom

Initial logical budgets on a 1 TB disk are: application PostgreSQL 22 percent, Neo4j 12 percent, ClickHouse 28 percent, MinIO 8 percent, backups 15 percent, Redis/local logs 2 percent, and at least 13 percent reserve. Operators may lower component budgets, but configured maxima plus reserve cannot exceed the managed filesystem.

High and critical watermarks default to 80 and 90 percent. High state halves scheduled ingestion concurrency (minimum one), suppresses optional excerpts for successful work, and runs supported cleanup; it returns to normal only after usage stays at or below 75 percent for 15 minutes. Critical state pauses new scheduled/nonessential ingestion and remains until usage stays at or below 85 percent for 15 minutes, then degrades to high. Cleanup timeout or failure preserves the current state and emits a correlated alert. Active safety, cleanup, alert, and restore work remain allowed. Database-owned files are never removed directly.

Target retention is 30 days for successful/partial detailed traces and 90 days for failed detailed traces and failed PostgreSQL attempt evidence. Native Langfuse retention is capability-detected. When outcome-specific supported deletion is unavailable, retain all traces up to 90 days while budgets permit; if the high watermark persists, pause nonessential ingestion rather than silently deleting failure evidence or modifying Langfuse schemas.

Why: failure evidence is most valuable, but a storage-saving policy must not corrupt ClickHouse or MinIO.

### D10. Backups and restores are first-class operations

Scheduled backups create durable maintenance operations and component stage spans for application PostgreSQL, Neo4j, Langfuse PostgreSQL, ClickHouse, MinIO, and non-secret configuration. Every artifact SHALL be encrypted with an OpenBao-managed age recipient before it leaves component-local storage, checksummed, quota-accounted, and retained by policy; a missing or invalid encryption key fails backup activation rather than producing plaintext. Rotation keeps old recipients available for the documented restore window. Restore drills target isolated volumes and validate application operation rows plus Langfuse trace metadata. Production acceptance requires an application PostgreSQL/queue RPO of at most 24 hours, component restore RTO of at most 2 hours, and full-stack RTO of at most 4 hours, measured from the declared failure/restore start to a passing correlated synthetic operation.

Why: observability that disappears during host recovery is not production observability.

### D11. Environment ownership is cutover-gated by one authority

This change implements and tests an environment-ownership epoch, authority fingerprint, scheduler gate, and claim-time compare-and-swap, but it does not activate GX-10 as mutation owner. A candidate whose configured authority fingerprint does not match the authoritative queue database SHALL remain passive. The separate cutover change MUST select one PostgreSQL authority reachable by both environments during the handoff, migrate/verify data as needed, and only then advance the epoch. Independent database-local epochs are explicitly insufficient. Every trace records environment, release, authority fingerprint, and epoch.

Rollback ordering is fixed: fence the current owner in the shared authority, verify the passive target against that authority, then enable target mutations. DNS or configuration changes alone never transfer ownership.

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
- A six-hour soak at 50 submitted operations per minute (or the measured production peak if higher) with p95 trace arrival under 5 seconds, exporter drops below 0.1 percent, zero missing failed/partial trace roots, and 90-day projected storage within component budgets with 20 percent headroom.

## References

- Langfuse OpenTelemetry compatibility: https://langfuse.com/docs/compatibility
- Langfuse masking: https://langfuse.com/docs/observability/features/masking
- Langfuse data retention: https://langfuse.com/docs/administration/data-retention
- Langfuse self-hosted backups: https://langfuse.com/self-hosting/configuration/backups
- Langfuse self-hosted hardening: https://langfuse.com/self-hosting/configuration/hardening
