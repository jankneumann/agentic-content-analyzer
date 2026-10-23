## ADDED Requirements

### Requirement: Mobile capture is GX-10 cutover-ready

The GX-10 mobile save API SHALL pass authenticated TLS ingress verification without receiving production traffic in this change. Railway-specific runtime identity SHALL not be required for capture, queueing, scheduling, alerts, or observability verification. Production routing changes remain owned by the separate cutover proposal.

#### Scenario: [MOBILE-001] Synthetic mobile save targets GX-10

- **WHEN** an authenticated synthetic mobile client submits a URL through the candidate GX-10 ingress
- **THEN** the GX-10 API creates a correlated non-production durable operation
- **AND** the response exposes the operation status URL and trace response header

#### Scenario: [MOBILE-003] Unauthenticated mobile save is rejected

- **WHEN** a mobile client submits through public ingress without a valid session or admin credential
- **THEN** the request is rejected before a durable operation is created
- **AND** the rejection is audited without exposing credential material

### Requirement: Exactly one environment schedules mutations

During GX-10 and Railway coexistence, one authoritative queue/control PostgreSQL database SHALL designate exactly one scheduler/mutation owner using an authority fingerprint and fenced environment epoch. Independent database-local epochs SHALL NOT be treated as a distributed fence. Passive environments MAY serve health or rollback verification but SHALL NOT run ingestion schedules or claim mutation jobs.

#### Scenario: [MOBILE-002] Passive Railway environment starts

- **WHEN** Railway is configured as rollback-passive
- **THEN** scheduled mutation startup and queue claims are disabled
- **AND** a bounded status endpoint reports passive ownership

#### Scenario: [MOBILE-004] Two environments request mutation ownership

- **WHEN** GX-10 and Railway present different authorities or epochs while attempting to schedule or claim mutation work
- **THEN** claim-time fencing permits only the owner recorded by the shared authoritative database
- **AND** the losing environment remains passive and reports the conflict
