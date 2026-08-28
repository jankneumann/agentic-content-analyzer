## ADDED Requirements

### Requirement: Queue records persist trace context and attempts

Queue storage SHALL add nullable, backward-compatible root operation and W3C submission-context fields to canonical job records and SHALL maintain an append-only bounded attempt evidence projection keyed by operation ID and claim generation. Indexes SHALL support exact trace lookup and ordered attempt lookup without placing trace identifiers into metric labels.

#### Scenario: [JOB-001] Claim atomically starts attempt evidence

- **WHEN** a worker successfully fences a queued job claim
- **THEN** the job claim and attempt evidence use the same claim generation
- **AND** the active attempt span is started from the stored submission context

#### Scenario: [JOB-002] Stale claim cannot overwrite evidence

- **WHEN** an older claimant reports progress or termination after a newer generation exists
- **THEN** the authoritative operation state rejects the stale write
- **AND** the stale attempt can only record a bounded stale-claim diagnostic on its own evidence row

### Requirement: Operation graph retention includes observability evidence

Retention SHALL preserve parent/child operation graphs and their bounded attempt evidence according to operation outcome. Cleanup SHALL delete by supported application transactions and SHALL not orphan terminal-event or audit correlations.

#### Scenario: [JOB-003] Failed evidence receives extended retention

- **WHEN** a failed operation exceeds successful-operation retention but not failed-operation retention
- **THEN** its bounded attempt evidence and correlation identifiers remain queryable
- **AND** unrelated successful detail may be removed

#### Scenario: [JOB-004] Cleanup preserves correlation integrity

- **WHEN** supported retention cleanup removes expired successful attempt evidence
- **THEN** parent/child operation rows, retained attempts, terminal events, and audit references remain valid
- **AND** cleanup does not delete database-owned files or bypass application transactions
