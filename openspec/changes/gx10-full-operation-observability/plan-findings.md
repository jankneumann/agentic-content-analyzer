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
