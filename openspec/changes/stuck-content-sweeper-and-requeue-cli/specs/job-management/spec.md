## ADDED Requirements

### Requirement: Queue claims carry fencing generations

Each queued-to-in-progress claim SHALL atomically increment `claim_generation`
at the database boundary. A database trigger on every transition to `queued`
SHALL reset claim protocol to the legacy value, and a compatible worker SHALL set
the current protocol while claiming.
All progress, heartbeat, cancellation, and terminal writes SHALL require the
current in-progress generation.

#### Scenario: Current worker updates lifecycle

- **WHEN** a worker writes with the generation it claimed and the row remains in progress
- **THEN** the lifecycle update SHALL succeed

#### Scenario: Superseded worker updates lifecycle

- **WHEN** a worker writes after generation changes or status becomes terminal/queued
- **THEN** the lifecycle update SHALL affect no row

#### Scenario: Old worker claims a previously compatible row

- **WHEN** a row is requeued after a protocol-2 attempt and then claimed by a worker that does not set the current protocol
- **THEN** the row SHALL retain the reset legacy protocol value
- **AND** reconciliation apply SHALL reject it as incompatible

#### Scenario: Every requeue path resets protocol

- **WHEN** retry, stale recovery, defer, or any legacy SQL changes a non-queued job back to `queued`
- **THEN** the database trigger SHALL set claim protocol to the legacy value in the same statement

### Requirement: Supported content writes validate operation claims

Supported parsing and summarization writers SHALL persist content ownership and
MUST validate both operation claim and content ownership before every domain
commit after acquisition. Initial or same-operation retry acquisition SHALL use
the narrower compare-and-swap defined by content-state reconciliation.

#### Scenario: Current claim commits content

- **WHEN** job generation and Content ownership both match
- **THEN** the supported writer MAY commit its phase transition or output

#### Scenario: New generation acquires a retained failed phase

- **WHEN** the current claim is generation N+1 and failed Content belongs to the same operation and phase at generation N
- **THEN** the writer MAY atomically renew ownership to N+1 before resuming
- **AND** it SHALL not renew ownership owned by another operation or phase

#### Scenario: Old computation reaches its commit after reclaim

- **WHEN** a newer job claim supersedes an older handler before its domain commit
- **THEN** the old writer's generation-guarded domain commit SHALL roll back
