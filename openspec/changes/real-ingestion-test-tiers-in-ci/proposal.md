# Change: Add real ingestion CI tiers

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `real-ingestion-test-tiers-in-ci`
> Effort: L
> Priority: 5

## Summary

Refine real ingestion coverage around `SOURCE_REGISTRY`, typed `IngestCommand`
models, canonical source fixtures, durable operations, and persisted terminal
results. Add a curated pull-request tier and a broader scheduled tier with
explicit credential and network-sensitivity policy.

## Dependencies

- `ri-03`

## Acceptance Outcomes

- The pull-request tier submits representative source commands through the
  canonical workflow service and verifies terminal results against database
  row deltas.
- The scheduled tier exercises credentialed or network-sensitive adapters with
  explicit skip and failure rules.
- Every source registry entry maps to a fixture tier or reviewed exclusion.
- Published operation/result evidence distinguishes adapter, queue, and
  persistence failures.

## Rationale

Mocked tests do not detect adapter, queue, database, and persistence failures
across the real ingestion boundary.
