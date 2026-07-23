# Add cross-surface release smoke tests

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `add-cross-surface-release-smoke-tests`
> Effort: L
> Priority: 4

## Summary

Add a deployed-environment compatibility gate spanning the frontend, CLI, and API. Separate production-safe read-only checks from staging or ephemeral mutation scenarios and record service revisions as promotion evidence.

## Dependencies

- `ri-01`
- `ri-02`

## Acceptance Outcomes

- The gate fails when a deployed frontend calls a retired workflow mutation.
- The gate exercises capability discovery and cursor omission through the frontend client contract and real CLI transport.
- A staging or ephemeral scenario submits a canonical ingestion request and observes its durable operation through a terminal state.
- Default configuration prevents mutating smoke scenarios from targeting production.
- Promotion documentation records the tested frontend and API revisions and links to retained evidence.

## Rationale

A release boundary test is needed to detect stale artifacts and contract skew before operators encounter retired routes or malformed requests.
