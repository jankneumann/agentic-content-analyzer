# Change: Reconcile stuck content states

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `stuck-content-sweeper-and-requeue-cli`
> Effort: L
> Priority: 8

## Summary

Create a narrow reconciliation workflow for content rows whose transitional
state conflicts with terminal or stale durable operations. Reuse operation
retry, cancellation, retry budgets, checkpoints, and idempotency wherever
possible.

## Dependencies

- `ri-07`

## Acceptance Outcomes

- Tested rules identify authoritative operation-to-content transitions and
  bounded retry behavior.
- Dry-run lists affected content and operations without mutation.
- Apply mode is idempotent/auditable and uses canonical operation retry when it
  can restore state.
- Repeated reconciliation cannot duplicate content, reset successful
  checkpoints, or exceed retry budgets.

## Rationale

Recovery must repair domain state without bypassing durable operations or
duplicating content.
