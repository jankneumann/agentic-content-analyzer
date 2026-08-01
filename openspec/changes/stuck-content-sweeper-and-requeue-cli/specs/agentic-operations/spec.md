## ADDED Requirements

### Requirement: Internal retry supports an optional atomic ceiling

The canonical operation service SHALL expose one connection-scoped retry
primitive that can enforce an optional retry-count ceiling in the lifecycle
UPDATE while preserving existing graph lock order, normalized input, parent
linkage, idempotency, and checkpoints.

#### Scenario: Reconciliation supplies a ceiling

- **WHEN** locked reconciliation retries a failed leaf below its ceiling
- **THEN** the same operation row SHALL become queued and increment once
- **AND** notification SHALL remain transactional with the caller

#### Scenario: Public manual retry omits a ceiling

- **WHEN** the existing operation retry API is called outside reconciliation
- **THEN** its compatibility behavior SHALL remain unchanged
- **AND** it SHALL reuse the same locked retry primitive

#### Scenario: Retry preserves a resumable operation result

- **WHEN** a failed canonical URL operation carries an exact-content webpage extraction checkpoint
- **THEN** retry SHALL preserve that result until the newer claim consumes and replaces it
- **AND** the handler SHALL not restart aggregate URL routing

#### Scenario: Retry validates URL resume evidence

- **WHEN** a result is considered for conditional preservation
- **THEN** it SHALL satisfy the closed strict-v2 URL resume profile from content-state reconciliation
- **AND** malformed, mismatched, zero-ID, or multi-ID results SHALL be cleared as ordinary stale results

#### Scenario: Retry sees an ordinary stale result

- **WHEN** a non-pipeline operation result is not the validated exact-content webpage extraction checkpoint
- **THEN** existing retry behavior SHALL continue clearing that stale result

#### Scenario: Locked caller uses the wrong connection order

- **WHEN** a caller has not acquired the graph/root locks on the supplied connection
- **THEN** the internal locked retry primitive SHALL reject or remain inaccessible to that caller
