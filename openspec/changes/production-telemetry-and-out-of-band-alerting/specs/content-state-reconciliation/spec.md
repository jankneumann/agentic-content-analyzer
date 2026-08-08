# content-state-reconciliation Specification Delta

## ADDED Requirements

### Requirement: Reconciliation telemetry follows committed action evidence

Each committed reconciliation action SHALL create one terminal-event intent in
the same transaction as the content mutation and append-only action record.
Failed apply items SHALL record bounded failure evidence only after their item
transaction rolls back. Dry-run SHALL remain read-only and notification-free.

#### Scenario: Apply commits an action

- **WHEN** reconciliation commits a content mutation and action audit
- **THEN** exactly one event intent keyed by the immutable action ID SHALL commit
  in the same transaction

#### Scenario: Apply action rolls back

- **WHEN** an item mutation or audit insert fails
- **THEN** no applied-action event SHALL survive the rollback
- **AND** one bounded `apply_failed` event MAY be inserted afterward without raw
  exception text

#### Scenario: Apply is repeated

- **WHEN** the same run/action evidence is observed repeatedly or concurrently
- **THEN** uniqueness SHALL prevent duplicate terminal events and deliveries

#### Scenario: Dry-run inspects candidates

- **WHEN** reconciliation runs in dry-run mode
- **THEN** it SHALL create no terminal event, delivery, or notification row
