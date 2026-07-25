# Contracts: real-ingestion-test-tiers-in-ci

No new machine-readable interface contracts apply to this change. Sub-types evaluated:

- **OpenAPI**: none — the change adds CI test tiers over the existing canonical
  workflow; it introduces no new or modified HTTP endpoints. It consumes the existing
  `OperationService` / `/api/v1` durable-operation contract unchanged.
- **Database**: none — no schema changes. Approach A explicitly introduces no new
  table or run-state representation; it reads the existing operation/result records.
- **Events**: none — no new or modified events.
- **Type generation**: none — no contract inputs to generate from.

The behavioral contract for this change lives in `specs/real-ingestion-ci/spec.md`
(tier behavior, live-adapter policy, registry completeness, failure classification).
Failure classification derives from the existing durable operation/result problem
taxonomy owned by `OperationService`.
