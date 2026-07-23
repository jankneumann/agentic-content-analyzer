# Change: Reconcile persisted ingestion results

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `persisted-ingestion-run-results`
> Effort: L
> Priority: 7

## Summary

Map historical ingestion-run requirements to existing `pgqueuer_jobs`
operations, checkpoints, source results, resources, retries, idempotency, and
terminal problems. Add only demonstrably missing typed projections, history
filters, retention behavior, and canonical API or CLI queries.

## Dependencies

- `ri-05`
- `ri-06`

## Acceptance Outcomes

- Every original acceptance case maps to existing durable state or a specified
  remaining gap.
- Canonical API/CLI queries distinguish source-level success, partial,
  zero-item, and failed outcomes.
- Result-size and retention rules are deterministic and tested.
- Existing parent-child operations, retries, checkpoints, and idempotency remain
  authoritative.
- No parallel run table/state machine is introduced without a documented unmet
  query or retention requirement.

## Rationale

Operators need useful history without a second authoritative state model.
