# Plan Findings

## Iteration 1

Strict baseline validation passed. Two independent reviews produced overlapping findings; duplicates were consolidated below. All high/medium findings were resolved in the plan artifacts.

| # | Type | Criticality | Finding | Resolution |
|---|---|---|---|---|
| 1 | scope/consistency | high | The Impact section promised a new CLI/UI surface without requirements, tasks, or frontend scope. | Limited scope to diagnostic APIs consumed by the existing CLI and made a new frontend UI an explicit non-goal. |
| 2 | security/compatibility | high | The delta modeled only `AdminKey`, conflicting with the existing session-or-admin authorization behavior and omitting 401/403 responses. | Added session-cookie-or-admin security and explicit 401/403 responses while preserving exact-read policy. |
| 3 | completeness/performance | high | Attempt history stopped at 100 rows without a cursor or deterministic ordering. | Added limit/cursor parameters, ascending claim-generation order, continuation metadata, CORR-015, and API tasks/tests. |
| 4 | consistency | high | Nullable OperationContext fields disagreed across JSON Schema, OpenAPI, Python, and TypeScript. | Chose required-with-explicit-null semantics, made pre-claim attempt number nullable, aligned widths, and completed both generated review stubs. |
| 5 | consistency | high | Generated review stubs omitted page, extension, health, and problem models. | Completed both stubs and made durable workflow-registry generation plus drift validation task 1.1/1.2. |
| 6 | completeness/architecture | high | One process-local health object could not represent every API, worker, scheduler, and short-lived process. | Added a bounded PostgreSQL process-health projection and aggregate health page with timestamps, ages, freshness, capacity, drop, and flush evidence. |
| 7 | security/performance | high | SQL diagnostic arrays admitted unbounded/non-string values. | Contracted a bounded diagnostic-code domain/array with item regex, cardinality, and total byte limits. |
| 8 | consistency | high | Specs implied durable intermediate-stage history while SQL stored only a terminal stage. | Explicitly limited PostgreSQL to one attempt summary and kept detailed stage history in Langfuse. |
| 9 | correctness | high | `ON DELETE SET NULL`/cascade cleanup could destroy correlation needed by retained failed evidence. | Switched root correlation to retention-ordered restriction and specified parent/root tombstone lifetime plus JOB-004. |
| 10 | performance/testability | high | Excerpt, buffer, trace-volume, latency, drop, soak, and storage acceptance bounds were absent. | Added concrete byte/span/buffer limits and a six-hour, 50-operations/minute acceptance gate with latency/drop/failure/storage thresholds. |
| 11 | resilience/testability | high | Watermark actions lacked hysteresis, resume, cleanup-failure, and capability-gap behavior. | Defined 80/90 entry, 75/85 timed recovery, concurrency/pause actions, cleanup failure behavior, and failure-preserving fallback scenarios. |
| 12 | security/testability | high | Secret rotation and mandatory backup encryption were not implementable or tested. | Selected OpenBao plus age encryption, fail-closed key behavior, rotation semantics, and GX10-014/GX10-015 tests. |
| 13 | feasibility/parallelizability | high | Contract, queue-lifecycle, ingestion, operational, audit, and integration package scopes omitted actual owned files. | Mapped durable contracts and runtime paths to owners, split provider vs non-HTTP coverage, serialized overlaps, and revalidated the DAG. |
| 14 | testability | high | Package commands did not produce declared JUnit/quality/acceptance evidence. | Added JUnit paths and explicit contract, static-quality, acceptance, and strict-validation steps; task 11.1 now owns integration. |
| 15 | completeness/scope | high | Mobile ingress and GX-10-primary requirements contradicted the no-cutover non-goal. | Made the stack cutover-ready only, added synthetic authenticated/unauthorized ingress tests, and deferred traffic/data activation to an unapproved follow-up proposal. |
| 16 | architecture/assumptions | high | Independent Railway/GX-10 databases cannot enforce one ownership epoch, and host runtime choices were unspecified. | Required one shared authority fingerprint/epoch for any later handoff, refused independent authorities, and selected Compose V2 + systemd + Caddy + OpenBao + `/srv/aca` logical storage governance. |
| 17 | clarity/consistency | medium | Claim generation and attempt number had undefined relationship and width. | Preserved 64-bit generation width; pre-claim attempt is null and claimed attempt number equals claim generation plus one. |

### Parallelizability

- Independent root packages: 1 (`wp-contracts`)
- Sequential dependency chains: 4 principal chains through the core spine
- Maximum parallel width: 4 packages
- Declared file-overlap conflicts: none after dependency ordering; semantic scopes now include durable contracts, workflows, storage, lifecycle, and real audit/terminal files
- Validation: work-package schema, dependency references, DAG cycles, lock keys, scheduler scope/lock checks all pass

### Residual below-threshold items

- The six-hour soak is intentionally expensive; it remains an acceptance task rather than a per-package unit gate.
- OS project quotas remain optional defense in depth; the portable requirement is the validated dedicated filesystem plus logical/native-service budgets.

## Iteration 2

The independent PLAN_REVIEW produced twelve blocking findings. All were fixed inline and revalidated before another review round.

| # | Finding | Resolution |
|---|---|---|
| 1 | Nullable response members drifted across OpenAPI and generated stubs. | Made every frozen nullable response member required-with-null consistently. |
| 2 | JavaScript `number` could corrupt 64-bit attempt identities. | Encoded claim generations, attempt numbers, epochs, and cursors as canonical decimal strings at JSON/TypeScript boundaries while retaining PostgreSQL BIGINT. |
| 3 | Process-health SQL lacked required-observability and bounds. | Added the flag, enums/patterns, buffer-capacity invariant, freshness index, 24-hour/7-day cleanup classes, and deterministic 1,000-row cap. |
| 4 | Audit correlation lacked checks, references, and indexes. | Added trace/span validation, retention-safe operation reference, and trace/operation indexes. |
| 5 | Attempt span nullability and numbering conflicted. | Made root span required-with-null and attempt number a positive canonical decimal string with runtime `generation + 1` validation. |
| 6 | Normal sessions could reach privileged diagnostics. | Added a distinct operator capability for attempt history, deployment health, ownership status, and Langfuse links; exact reads retain their current policy with privileged links nulled. |
| 7 | Coverage inventory occurred after package scope freeze. | Added `contracts/operation-entrypoints.yaml` at contract freeze and expanded operational scope to all CLI commands, operational scripts, clients, MCP, agents, schedulers, backup, cleanup, and alerts. |
| 8 | Contract package could not wire CI. | Added Makefile, generator, and CI workflow paths and locks to `wp-contracts`. |
| 9 | Ownership status/dry run was not frozen. | Added operator-authorized OpenAPI schemas and conflict semantics with fingerprint redaction. |
| 10 | Host firewall could not safely enforce hostname egress. | Selected a fail-closed authenticated CONNECT proxy; application networks have no direct Internet route and bounded DNS/NTP/bootstrap exceptions are tested. |
| 11 | Process instances could accumulate without bound. | Added freshness index, TTL cleanup, deterministic cap, restart-churn scenario, and acceptance tests. |
| 12 | Restore measurements had no pass/fail objectives. | Set application PostgreSQL/queue RPO <=24h, component RTO <=2h, and full-stack RTO <=4h. |
| 13 | Submission context admitted unknown/secret-like keys. | Added a SQL key allowlist plus application serializer and direct-SQL negative test requirements. |

Validation: strict OpenSpec, JSON Schema metaschema, YAML/JSON parsing, and all six work-package schema/DAG/lock/scope checks pass.

## Iteration 3

PLAN_REVIEW round 2 identified ten final blockers; all were fixed inline before the third review.

- Signed-BIGINT decimal strings now enforce the exact maximum, claimed generation reserves `+1` headroom, and generated/JSON boundary tests cover max, max+1, and overflow.
- SQL now constrains indexed queue correlation fields equal to the canonical context envelope.
- Process health persists lifecycle kind and expiry; cleanup removes expired rows only and reports nonexpired rows omitted from the 1,000-row response cap.
- The API/audit package owns the operator capability setting and negative authorization tests; GX-10 runtime depends on it and wires OpenBao rotation.
- Every current top-level executable script is mechanically classified as instrumented/bootstrap or explicitly pure deterministic tooling; bootstrap operations use a masked hash-chained local spool imported after PostgreSQL readiness.
- Ingestion and operational packages own every test path they execute, and integration scope is mechanically validated as a superset of every predecessor write scope.
- The resumable soak owns its runner/validator/tests/evidence and has a 480-minute timeout/lease for the six-hour run.
- The unenforceable distributed 2 MiB trace cap was replaced by per-observation and process-local-attempt budgets with reserved failure/security/backup evidence and deterministic omission order.
- The runtime now freezes Squid 6.13, immutable image-digest enforcement, OpenBao credentials, syntax-validated policy reload, masked logs, readiness, and fail-closed application-network dependencies.
- Static/contract integration steps create their declared evidence files while preserving pipeline exit status.

Validation: strict OpenSpec passes; all work-package schema/reference/DAG/lock/scope checks pass; JSON Schema metaschema checks pass; all current scripts are classified; integration covers the complete predecessor union; and generated signed-BIGINT boundary tests pass.
