# Change: Add real ingestion CI tiers

> Parent roadmap: `roadmap-workflow-surface-reliability` (item `ri-05`)
> Change ID: `real-ingestion-test-tiers-in-ci`
> Effort: L
> Priority: 5
> Depends on: `ri-03` (completed)

## Why

Mocked ingestion tests pass while the real boundary — adapter → queue → database →
persistence — silently breaks in production. The codebase already has the seams to
close this gap but no CI tier exercises them end-to-end:

- `SOURCE_REGISTRY` (`src/ingestion/registry.py`) defines 18 typed `IngestCommand`
  descriptors, but nothing submits representative commands through the canonical
  workflow service and checks the persisted result.
- `tests/fixtures/sources/library.py` already holds a `SOURCE_FIXTURES` registry and
  `assert_fixture_registry_complete()` (registry↔fixture parity), and
  `tests/fixtures/sources/harness.py` runs commands against a real DB `Session` — yet
  these are not wired into a dedicated real-ingestion CI gate.
- The one live pattern (`tests/integration/test_arxiv_live.py`, `-m live_api`) covers a
  single source with ad-hoc skip logic; there is no policy-driven tier for
  credentialed or network-sensitive adapters.

Operators cannot today tell an adapter failure (bad parse, upstream 4xx) from a queue
failure (job never ran) from a persistence failure (rows not written) — the durable
operation/result records carry this information but CI never surfaces it.

## What Changes

Two new CI tiers over the canonical durable workflow, plus completeness and evidence:

1. **Pull-request tier** (per PR, offline, deterministic): submit ~6 representative
   typed source commands (rss, gmail, url, youtube-playlist, arxiv-search, blog)
   through `OperationService`, observe each durable operation to a terminal state, and
   assert the claimed result against real database row deltas on the existing
   `paradedb` CI Postgres service via the deterministic harness.
2. **Scheduled tier** (cron, broader): run all 18 fixture-backed sources, and
   additionally hit **live** adapters where policy allows —
   free/no-key (arxiv, rss, url, hugging-face) and credentialed-non-paid (gmail,
   youtube, substack, scholar, readwise) when the secret is present, else skip with an
   explicit reason. Paid APIs (x-search/Grok, perplexity) are a **reviewed live
   exclusion** — fixture-tested only.
3. **Registry completeness**: every `SOURCE_REGISTRY` entry maps to a fixture tier or a
   reviewed exclusion, enforced at collection time (extend the existing parity assert
   with an explicit, documented exclusion set).
4. **Failure-class evidence**: CI publishes evidence derived from the durable
   operation/result records that distinguishes **adapter vs queue vs persistence**
   failures, so a red run points at the layer that broke.

Out of scope (downstream items): a persisted run-history query surface (`ri-07`),
CLI gen-eval scenarios (`ri-06`), and any new run-state table.

## Acceptance Outcomes

- The pull-request tier submits representative source commands through the canonical
  workflow service and verifies terminal results against database row deltas.
- The scheduled tier exercises credentialed or network-sensitive adapters with explicit
  skip, retry, and failure rules.
- Every source registry entry maps to a fixture tier or a reviewed exclusion.
- Published operation/result evidence distinguishes adapter, queue, and persistence
  failures.

## Approaches Considered

### Approach A: Pytest-marker tiers over the existing harness — **Recommended**

Add pytest markers (a `real_ingest` family, with live adapters env-gated) and a new
test module that drives the existing `SOURCE_FIXTURES` + DB-backed harness through
`OperationService`, asserting terminal durable results and DB row deltas. Two CI jobs
(a per-PR job and a scheduled workflow) select the tier by marker/env. Failure
classification reuses the **durable operation/result problem taxonomy** already
recorded by `OperationService`; a thin reporter emits a CI summary grouping failures by
adapter/queue/persistence.

- **Pros**: Maximum reuse (fixtures, parity assert, harness, operation taxonomy all
  exist); no parallel evidence schema (aligns with `ri-07`'s "no second run-state"
  rule); smallest new surface; markers match repo convention (`live_api`, `integration`).
- **Cons**: Evidence is a derived CI summary, not a standalone versioned artifact;
  live-adapter policy lives in test/config code rather than a declarative contract.
- **Effort**: M

### Approach B: Standalone runner + versioned evidence artifact (RI-04 style)

Build a dedicated runner (mirroring RI-04's `release_smoke`) that submits commands via
`OperationService`, collects a structured, schema-validated JSON evidence artifact
classifying every source's outcome (adapter/queue/persistence), and is invoked by both
CI jobs. Evidence lands in `openspec/contracts/real-ingestion-ci/`.

- **Pros**: Rich, versioned, auditable evidence; declarative live/exclusion policy;
  consistent with RI-04's evidence discipline.
- **Cons**: Significant new code duplicating what the operation/result records already
  encode; risks a parallel result representation that `ri-07` is meant to own; higher
  effort for evidence that pytest + the operation taxonomy already provide.
- **Effort**: L

### Approach C: Hybrid — markers for tiers, small evidence contract for classification

Approach A's marker/harness tiers, plus a minimal JSON evidence file (not a full
runner) summarizing per-source adapter/queue/persistence outcomes, checked into CI
artifacts and validated by a lightweight schema.

- **Pros**: Reuses harness like A; adds just enough durable evidence for operators
  without a full runner.
- **Cons**: Introduces a small evidence schema whose ownership overlaps `ri-07`;
  two sources of truth (pytest result + evidence JSON) to keep in sync.
- **Effort**: M

**Recommendation**: **Approach A.** The fixture registry, parity assert, DB harness,
and durable operation/result problem taxonomy already exist — A wires them into two
policy-driven CI tiers with the least new code and, critically, keeps failure
classification anchored in the durable operation model rather than a parallel evidence
schema. That respects `ri-07`'s boundary (no second run-state/representation) and lets
`ri-07` later build the operator-facing history surface on the same records. B/C are
preferable only if we decide CI must emit a standalone versioned ingestion-evidence
contract now, which the roadmap defers.

### Selected Approach

**Approach A — pytest-marker tiers over the existing harness** (confirmed at Gate 1).

Confirmed scope decisions:
- PR tier exercises 6 representative sources: `rss`, `gmail`, `url`,
  `youtube-playlist`, `arxiv-search`, `blog`.
- Scheduled tier runs all 18 fixture-backed sources, and hits **live** adapters for
  free/no-key (`arxiv`, `rss`, `url`, `hugging-face`) and credentialed-non-paid
  (`gmail`, `youtube`, `substack`, `scholar`, `readwise`) when the secret is present,
  else skip-with-reason.
- Paid APIs (`x-search`/Grok, `perplexity`) are a **reviewed live exclusion** —
  fixture-tested only, never hit live in CI.
- DB-delta verification runs against the existing `paradedb` CI Postgres service via
  the deterministic harness.
- Failure classification reuses the durable operation/result problem taxonomy; no new
  schema or run-state table is introduced.
