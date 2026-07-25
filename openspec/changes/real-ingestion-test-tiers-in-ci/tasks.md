# Tasks: Real ingestion test tiers in CI

> Change ID: `real-ingestion-test-tiers-in-ci`
> Approach: A (marker tiers + operation taxonomy)

## Status

- [x] Planning
- [ ] Implementation
- [ ] Testing
- [ ] Review
- [ ] Done

## Phase 1 — PR tier: durable submission + DB-delta verification

- [x] 1.1 Write PR-tier tests for the 6 representative sources (rss, gmail, url,
  youtube-playlist, arxiv-search, blog): submit each fixture command via
  `OperationService`, observe terminal operation, assert `Content` row delta. (RED)
  **Spec scenarios**: real-ingestion-ci — "Representative fixture ingestion completes
  and matches the DB delta", "A terminal operation claims results that the database did
  not persist"
  **Design decisions**: D1 (OperationService), D2 (persistence classification)
  **Dependencies**: None — **Size: M**
- [x] 1.2 Add a real-ingestion harness path that routes a `SOURCE_FIXTURES` command
  through `OperationService` and drains the durable queue to a terminal state
  in-test (bounded worker drain helper if needed per design risk).
  **Design decisions**: D1
  **Dependencies**: 1.1 — **Size: M**
- [x] 1.3 Add a DB-delta assertion helper (expected vs actual `Content` rows for a
  submitted operation) reused by all tier tests.
  **Dependencies**: 1.1 — **Size: S**
- [x] Checkpoint: run PR-tier tests against the paradedb service, review diff, verify
  scope stays within `tests/real_ingestion/` + `tests/fixtures/sources/`

## Phase 2 — Registry completeness

- [x] 2.1 Write a collection-time test asserting every `SOURCE_REGISTRY` entry maps to
  a `SOURCE_FIXTURES` fixture or the reviewed exclusion set, and that no exclusion
  names an unknown source. (RED)
  **Spec scenarios**: real-ingestion-ci — "A new registry source has no fixture and no
  exclusion", "The exclusion set references an unknown source"
  **Design decisions**: D5
  **Dependencies**: None — **Size: S**
- [x] 2.2 Add the reviewed exclusion set (with reasons) and wire
  `assert_fixture_registry_complete()` into real-ingestion collection.
  **Design decisions**: D5
  **Dependencies**: 2.1 — **Size: S**

## Phase 3 — Failure-class evidence

- [x] 3.1 Write tests for the failure classifier: adapter vs queue vs persistence,
  each derived from durable operation/result records (including the "adapter error not
  misreported as persistence" case). (RED)
  **Spec scenarios**: real-ingestion-ci — "A run summary attributes each failure to a
  layer", "An adapter error is not misreported as a persistence failure"
  **Design decisions**: D2
  **Dependencies**: 1.2 — **Size: M**
- [x] 3.2 Implement the classifier (pure function over operation/result records) and a
  CI summary reporter that renders per-source classifications.
  **Design decisions**: D2
  **Dependencies**: 3.1 — **Size: M**
- [x] Checkpoint: run Phase 2–3 tests, review diff, confirm no new schema/table added

## Phase 4 — Scheduled tier + live-adapter policy

- [x] 4.1 Write tests for the live-adapter policy table: credentialed source skips with
  a reason when its secret is absent; paid APIs are never live-eligible. (RED)
  **Spec scenarios**: real-ingestion-ci — "A credentialed adapter runs live when its
  secret is present", "A credentialed adapter is skipped when its secret is absent",
  "A paid API is never called live"
  **Design decisions**: D4
  **Dependencies**: 2.2 — **Size: M**
- [x] 4.2 Implement the live-adapter policy table (credential env vars, live-eligible,
  retry, paid-exclusion) and env-gated live execution for the scheduled tier.
  **Design decisions**: D4
  **Dependencies**: 4.1 — **Size: M**
- [x] Checkpoint: run full `-m real_ingest` suite with `REAL_INGEST_LIVE=0`, review diff

## Phase 5 — CI wiring + docs

- [x] 5.1 Register the `real_ingest` marker in `pyproject.toml` and add it to the unit
  `test` shard deselection filter so default shards don't run it.
  **Design decisions**: D3
  **Dependencies**: 1.1 — **Size: S**
- [ ] 5.2 Add the PR-tier CI job (`pytest -m real_ingest`, `REAL_INGEST_LIVE=0`,
  paradedb service) to `.github/workflows/ci.yml` as a required-eligible check.
  **Design decisions**: D3
  **Dependencies**: 5.1, 1.2, 1.3 — **Size: S**
- [ ] 5.3 Add the scheduled workflow (`.github/workflows/real-ingestion-scheduled.yml`,
  `schedule` + `workflow_dispatch`, `REAL_INGEST_LIVE=1`) running the full set + policy
  live adapters, uploading the failure-class summary.
  **Design decisions**: D3, D4
  **Dependencies**: 4.2, 3.2 — **Size: S**
- [ ] 5.4 Update `docs/TESTING.md` with the two tiers, the marker, the live policy, and
  the exclusion set.
  **Dependencies**: 5.2, 5.3 — **Size: S**
- [ ] Checkpoint: `openspec validate real-ingestion-test-tiers-in-ci --strict`, run the
  PR tier locally, review full diff for scope
