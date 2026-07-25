# Design: Real ingestion CI tiers

## Context

Approach A (Gate 1): pytest-marker tiers over the existing fixture registry and
DB-backed harness, with failure classification anchored in the durable operation/result
problem taxonomy. No new schema, runner, or run-state table.

Existing seams reused:
- `src/ingestion/registry.py::SOURCE_REGISTRY` — 18 typed `SourceDescriptor` entries.
- `tests/fixtures/sources/library.py` — `SOURCE_FIXTURES` + `assert_fixture_registry_complete()`.
- `tests/fixtures/sources/harness.py` — DB-backed harness over a real `Session`.
- `OperationService` — canonical durable submission + terminal operation/result records.
- CI `test` job's `paradedb` Postgres service.

## Decisions

### D1: Submit through OperationService, not IngestionService directly

The harness today drives `IngestionService` directly. The PR/scheduled tiers MUST route
representative commands through `OperationService` (the canonical durable workflow) so
the test exercises the same submission → queue → worker → persistence path production
uses, and can observe a real terminal *operation/result*, not just a service return.
Rationale: the acceptance outcome is "through the canonical workflow service"; a direct
`IngestionService` call would skip the queue/worker boundary where real failures hide.

### D2: Failure classification derives from the durable operation/result problem taxonomy

A source outcome is classified by reading its persisted operation/result record:
- **adapter** — operation terminated with an adapter/source-level problem (upstream
  HTTP/parse error), zero `Content` rows written.
- **queue** — operation never reached a worker / no terminal transition within the
  tier deadline (job dispatch/queue failure).
- **persistence** — operation claims success but expected `Content` rows are absent, or
  a DB write error is recorded.

No new evidence schema or table (respects `ri-07`'s ownership of the result surface).
The classifier is a pure function over existing records; the CI "evidence" is a rendered
summary of those classifications.

### D3: Tier selection by pytest marker + env gate

- New marker `real_ingest` (registered in `pyproject.toml`), added to the unit-shard
  deselection filter so the default `test` shards do not run it.
- PR tier: a dedicated CI job runs `pytest -m real_ingest` with live adapters disabled
  (`REAL_INGEST_LIVE=0`), restricted to the 6 representative sources.
- Scheduled tier: a `workflow_dispatch` + `schedule` workflow runs the full fixture set
  and, with `REAL_INGEST_LIVE=1`, the policy-permitted live adapters.

### D4: Live-adapter policy is a declarative table

A per-source policy table (source key → {credential env var(s), live-eligible bool,
cadence, retry, paid-exclusion bool}) drives skip/retry/exclusion. Missing credential →
skip-with-reason; paid (`x-search`, `perplexity`) → `live_eligible=False` permanently.
The table is the single source of truth the parity/exclusion assert reads.

### D5: Registry completeness via the existing parity assert + a reviewed exclusion set

Extend usage of `assert_fixture_registry_complete()` so collection fails when a registry
entry has neither a `SOURCE_FIXTURES` fixture nor a documented exclusion, and fails when
the exclusion set names an unknown source. Exclusions carry a recorded reason.

## L-task decomposition

The one L-sized area — "real-ingestion tier harness + PR tier" — is split into three
M/S tasks in `tasks.md` (harness routing through OperationService; DB-delta assertion
helper; the 6 representative PR-tier tests) so no single task exceeds M. The remaining
areas (completeness, evidence, scheduled/live policy, CI wiring) are independently
S/M-sized.

## Risks / open questions

- **Queue execution in CI**: submitting through `OperationService` requires the durable
  worker to run in-process (or a synchronous drain) within the CI test. Task 1.2 must
  confirm the harness can drain the queue deterministically without the full worker
  daemon; if not, add a bounded in-test worker drain helper.
- **Which CI secrets exist**: the scheduled tier's live set is gated per-secret at
  runtime, so absent secrets degrade to skips — no plan change needed, but the initial
  live coverage depends on which secrets are configured in the repo.
