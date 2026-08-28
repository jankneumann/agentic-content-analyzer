## Purpose

Define a production-grade local GX-10 runtime for all internal application and observability services while preserving controlled external API access and rollback safety.

## ADDED Requirements

### Requirement: Complete internal GX-10 topology

The production GX-10 deployment SHALL run the API, worker pools, scheduler, maintenance jobs, PostgreSQL, Redis, Neo4j, Langfuse web and worker, ClickHouse, and MinIO on managed local services with pinned versions, persistent volumes, health checks, restart policy, and declared dependencies.

#### Scenario: [GX10-001] Cold host restart restores services

- **WHEN** the GX-10 restarts without operator interaction
- **THEN** stateful dependencies become healthy before dependent application services become ready
- **AND** queued operations and persisted telemetry remain available

#### Scenario: [GX10-002] One internal dependency is unhealthy

- **WHEN** PostgreSQL, Redis, Neo4j, ClickHouse, MinIO, or Langfuse is unavailable
- **THEN** dependent service readiness reports the degraded dependency
- **AND** restart loops use bounded backoff rather than consuming the host

### Requirement: One-terabyte storage governance

The deployment SHALL define configurable filesystem quotas and high/critical watermarks that fit within a 1 TB disk. The initial allocation SHALL reserve at least 13 percent free space and budget no more than 22 percent for application PostgreSQL, 12 percent for Neo4j, 28 percent for ClickHouse, 8 percent for MinIO, 15 percent for backups, and 2 percent for Redis and local service logs.

The system SHALL default to 30-day detailed retention for successful/partial traces and 90-day retention for failed traces and failed PostgreSQL attempt evidence. Where the installed Langfuse edition cannot enforce outcome-specific retention through supported interfaces, the controller SHALL retain all detailed traces for up to 90 days, report the capability gap, and continue enforcing watermarks without directly modifying Langfuse-owned schemas.

#### Scenario: [GX10-003] Disk reaches high watermark

- **WHEN** managed storage reaches the configured high watermark
- **THEN** ingestion concurrency and nonessential trace detail are reduced by documented policy
- **AND** retention/backup cleanup runs with auditable results
- **AND** failed-operation evidence is preserved ahead of successful trace detail

#### Scenario: [GX10-004] Disk reaches critical watermark

- **WHEN** managed storage reaches the configured critical watermark
- **THEN** new nonessential ingestion is paused
- **AND** the operator receives an alert correlated to a durable maintenance operation
- **AND** no database-owned files are deleted directly

### Requirement: Production secrets and network boundaries

Secrets SHALL be supplied by the repository's supported secret manager or protected environment files, SHALL never be committed, and SHALL be rotated independently. Stateful services SHALL not be publicly exposed. Langfuse SHALL require authentication, and service-to-service networks SHALL expose only required ports.

External model, transcription, feed, page, video, email, and notification APIs MAY remain reachable through explicit egress policy with timeouts, redacted telemetry, and provider-specific rate limits.

#### Scenario: [GX10-005] External provider call is traced safely

- **WHEN** a local worker calls an allowed external API
- **THEN** the span records provider, operation, duration, status, retry, and bounded usage metadata
- **AND** credentials, authorization headers, raw query secrets, and prohibited payloads are absent

#### Scenario: [GX10-006] Internal port exposure is audited

- **WHEN** deployment validation inspects listening services
- **THEN** PostgreSQL, Redis, Neo4j, ClickHouse, and MinIO data ports are reachable only from approved host or container networks
- **AND** any unexpected public binding fails validation

### Requirement: Backup and restore are operational capabilities

PostgreSQL, Neo4j, ClickHouse, MinIO, and configuration metadata SHALL have scheduled, bounded, correlated backup operations. Backups SHALL be encrypted where supported, checksummed, included in the storage budget, and periodically restored into an isolated validation target.

#### Scenario: [GX10-007] Scheduled backup completes

- **WHEN** the backup schedule runs
- **THEN** each component reports a correlated stage outcome and artifact checksum
- **AND** partial component failure makes the overall backup partial or failed rather than successful

#### Scenario: [GX10-008] Restore drill detects unusable backup

- **WHEN** an isolated restore drill cannot validate application and trace metadata
- **THEN** the drill fails with component-specific diagnostics
- **AND** the source production volumes remain untouched

### Requirement: GX-10 primary with bounded coexistence

The GX-10 SHALL be the primary target for internal services after validation. Railway MAY remain as a time-bounded rollback environment, but only one environment SHALL own scheduled mutations and ingestion leases at a time. Environment identity SHALL be present in every operation and trace.

#### Scenario: [GX10-009] Rollback environment is passive

- **WHEN** GX-10 is the active primary
- **THEN** Railway schedulers and mutation workers are disabled
- **AND** Railway health checks cannot claim GX-10 work

#### Scenario: [GX10-010] Controlled rollback occurs

- **WHEN** an operator activates the rollback procedure
- **THEN** mutation ownership is fenced before Railway workers start
- **AND** the transition and verification are recorded as correlated durable operations

### Requirement: Production observability startup gate

Before accepting production work, each application process SHALL validate unique service name, environment, release revision, local OTLP endpoint, Langfuse credentials/host, masking policy, and export health. The deployment SHALL provide a backend-neutral smoke test that proves one synthetic operation is visible in PostgreSQL, logs, and Langfuse by the same identifiers.

#### Scenario: [GX10-011] Trace-arrival smoke test passes

- **WHEN** the operator runs production verification
- **THEN** one synthetic queued operation crosses API and worker services
- **AND** the verifier locates matching PostgreSQL attempt evidence and Langfuse observations
- **AND** it confirms that injected secret canaries are absent

#### Scenario: [GX10-012] Trace-arrival smoke test times out

- **WHEN** matching detailed evidence does not arrive within the configured bound
- **THEN** verification fails with the last successful export time and affected service identity
- **AND** it does not report deployment readiness
