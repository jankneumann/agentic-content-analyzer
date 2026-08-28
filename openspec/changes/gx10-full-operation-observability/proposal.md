## Why

The backend already has durable PostgreSQL operations, structured logs, OpenTelemetry, and Langfuse, but those systems do not share an attempt-aware correlation contract: trace context stops at queue submission, workers can run without telemetry, exact operations cannot locate their traces, and some ingestion failures are misclassified as successful skips. This must be corrected before the API, workers, schedulers, databases, storage, graph services, and observability stack become a production system on the local GX-10, where one operation must remain diagnosable across service restarts and external API calls.

## What Changes

- Define one canonical, W3C-compatible operation context for HTTP, CLI, MCP, scheduler, queue, worker, child-operation, ingestion-item, persistence, indexing, graph, delivery, maintenance, backup, alert, agent, and external-provider boundaries.
- Correlate each execution attempt using operation, root/parent operation, claim generation, trace, span/observation, service instance, release, stage, resource, and sanitized diagnostic identifiers.
- Persist bounded, indexed, restart-safe correlation and stage/outcome evidence in PostgreSQL while keeping `pgqueuer_jobs` authoritative for workflow state; no second operation state machine is introduced.
- Capture rich but controlled Langfuse traces: nested stage spans, full exception stack evidence, timings, retry/fallback decisions, model/token/cost metadata, and bounded redacted input/output excerpts. Secrets and unrestricted source content are excluded.
- Make failures truthful at their source, starting with YouTube exceptions currently reported as skips and blog failures that lack consistent stage/trace evidence.
- Expose safe trace correlation and lookup information on exact operation, terminal-event, audit, and diagnostic surfaces while retaining bounded collection responses and low-cardinality metrics.
- Make telemetry initialization and propagation consistent for API, standalone worker, CLI-started worker, scheduler, and maintenance processes; required telemetry failures become visible health/readiness degradation rather than silent trace loss.
- Provide a production-ready GX-10 topology for the application services, PostgreSQL, graph database, Langfuse, ClickHouse, Redis, and MinIO with authenticated secrets, persistent volumes, health checks, restart policy, backup/restore, quotas, and retention controls sized for a 1 TB disk.
- Use configurable retention with an initial target of 30 days for complete traces and 90 days for failed traces and failed PostgreSQL operation evidence, enforced by storage quotas and observable cleanup.
- Keep external model and content-provider APIs supported and trace their calls without exposing credentials or prohibited payloads.
- Supersede Railway-specific Langfuse proof with backend-neutral trace-arrival and end-to-end correlation verification usable on the GX-10 and during rollback coexistence.

## Capabilities

### New Capabilities

- `cross-service-operation-correlation`: Canonical operation context, attempt-aware propagation, durable PostgreSQL evidence, Langfuse correlation, stage/error vocabulary, and exact-operation diagnostics across all execution boundaries.
- `gx10-production-runtime`: Production requirements for running the complete internal service and observability topology on the GX-10, including storage budgets, retention, health, secrets, persistence, backup, restore, and external-API connectivity.

### Modified Capabilities

- `observability`: Extend Langfuse/OTel coverage from selected pipeline and LLM spans to every meaningful execution path, with explicit controlled-detail, redaction, retention, and trace-delivery health requirements.
- `agentic-operations`: Add safe trace/attempt correlation to canonical operation submission, child operations, exact reads, problems, and terminal evidence without changing PostgreSQL operation authority.
- `job-management`: Propagate W3C context through queue records and worker claims, distinguish retry attempts by claim generation, and retain bounded stage evidence across restarts.
- `pipeline`: Require one navigable parent/child trace topology across pipeline stages and source operations.
- `audit-log`: Persist actual trace/span correlation in addition to request identity and enrich active operation traces safely.
- `youtube-ingestion`: Distinguish skipped, filtered, duplicate, retryable failure, permanent failure, and success outcomes so exceptions cannot become successful skips.
- `blog-scraping`: Require stage-classified, operation-correlated discovery, fetch, extraction, filtering, and persistence diagnostics.
- `profile-configuration`: Add a production GX-10 profile with explicit local telemetry endpoints, unique service identities, and validation that prevents silent incomplete observability.
- `mobile-cloud-infrastructure`: Replace Railway-only production assumptions with a GX-10 primary topology and a bounded coexistence/rollback boundary.

## Approaches Considered

### Selected Approach: Contract-first dual-layer correlation spine

Define a shared operation-context API and stable stage/error vocabulary first. Propagate it through every boundary; store compact authoritative correlation/evidence in PostgreSQL and export rich nested execution evidence to Langfuse, with logs joined by the same trace and attempt identifiers.

**Pros**

- Preserves PostgreSQL as workflow truth while making Langfuse the detailed diagnostic system.
- Survives queue delays, retries, child operations, process restarts, and multi-service execution.
- Provides useful diagnosis when either Langfuse or an individual service is temporarily unavailable.
- Supports phased adapter instrumentation after shared contracts are frozen.

**Cons**

- Requires coordinated schema, queue, API, telemetry, and deployment changes.
- Needs careful sampling, redaction, cardinality, retention, and backpressure design.
- The highly coupled core propagation path must be implemented largely in sequence.

**Effort:** L

The user approved this approach at Gate 1 without modifications. It best matches the underlying requirement: from any operation ID, diagnose every attempt and service hop even after a restart, while keeping detailed evidence in Langfuse and the minimum safe, queryable facts in PostgreSQL. It also fits the 1 TB GX-10 budget better than duplicating all trace payloads in PostgreSQL and is more resilient than relying on Langfuse as the only failure record.

### Alternatives Not Selected

- **Langfuse-primary tracing with a PostgreSQL trace pointer (M):** smaller and faster, but rejected because trace-export loss would leave durable operations with insufficient diagnostic evidence.
- **PostgreSQL-first execution event ledger with Langfuse projection (L):** maximally queryable, but rejected because it duplicates high-volume trace data and risks becoming a second workflow state machine.

## Impact

- **Contracts and database:** canonical workflow OpenAPI/types, `pgqueuer_jobs` correlation fields or attempt projections, audit/terminal-event joins, Alembic migrations, indexes, cleanup, and backup coverage.
- **Runtime core:** API middleware, operation submission, queue payload/claim handling, worker entrypoints, execution-claim context, workflow handlers, settings/profiles, structured logging, OTel setup, and Langfuse provider behavior.
- **Execution adapters:** ingestion orchestrators and clients, YouTube/blog adapters, parsers, LLM routing, indexing, graph work, delivery, schedulers, maintenance, backup, alerts, and agent tasks.
- **Operator surfaces:** exact operation and diagnostic APIs/CLI/UI, health/readiness, local Compose/system service definitions, retention/storage dashboards, and runbooks.
- **Validation:** propagation and failure-classification contract tests, restart/retry integration tests, trace-arrival verification, redaction tests, storage/retention tests, and end-to-end GX-10 smoke scenarios.
- **Compatibility:** additive operation contracts during Railway/GX-10 coexistence; legacy rows remain readable with absent correlation fields. External APIs remain supported.
