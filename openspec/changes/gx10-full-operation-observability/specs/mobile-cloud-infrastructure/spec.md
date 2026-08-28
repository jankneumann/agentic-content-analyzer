## ADDED Requirements

### Requirement: Mobile capture supports GX-10 primary deployment

The mobile save API SHALL remain reachable through an authenticated TLS ingress while the application and stateful services run on the GX-10. Railway-specific runtime identity SHALL not be required for capture, queueing, scheduling, alerts, or observability verification.

#### Scenario: [MOBILE-001] Mobile save targets GX-10

- **WHEN** an authenticated mobile client submits a URL through the configured public ingress
- **THEN** the GX-10 API creates a correlated durable operation
- **AND** the response exposes the operation status URL and trace response header

### Requirement: Exactly one environment schedules mutations

During GX-10 and Railway coexistence, deployment configuration SHALL designate exactly one scheduler/mutation owner using a fenced environment epoch. Passive environments MAY serve health or rollback verification but SHALL NOT run ingestion schedules or claim mutation jobs.

#### Scenario: [MOBILE-002] Passive Railway environment starts

- **WHEN** Railway is configured as rollback-passive
- **THEN** scheduled mutation startup and queue claims are disabled
- **AND** a bounded status endpoint reports passive ownership
