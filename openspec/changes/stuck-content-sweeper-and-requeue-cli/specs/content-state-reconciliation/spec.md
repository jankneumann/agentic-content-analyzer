## ADDED Requirements

### Requirement: Content reconciliation follows durable operation authority

The system SHALL reconcile inconsistent transitional content state using
explicit operation-to-content rules, bounded retry budgets, checkpoints,
idempotency, and canonical operation controls.

#### Scenario: Dry-run finds inconsistent content

- **WHEN** reconciliation identifies a content row inconsistent with its
  terminal or stale operation
- **THEN** dry-run SHALL list both identifiers and the proposed transition
- **AND** SHALL perform no mutation

#### Scenario: Apply mode repairs recoverable state

- **WHEN** canonical operation retry can restore the content state
- **THEN** apply mode SHALL invoke that retry idempotently
- **AND** SHALL not duplicate content, reset a successful checkpoint, or exceed
  the retry budget
