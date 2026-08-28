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

The system SHALL default to 30-day detailed retention for successful/partial traces and 90-day retention for failed traces and failed PostgreSQL attempt evidence. At 80 percent usage it SHALL enter high state, halve scheduled-ingestion concurrency to a minimum of one, suppress optional successful excerpts, and run supported cleanup; it SHALL return to normal only after 15 minutes at or below 75 percent. At 90 percent it SHALL enter critical state and pause new scheduled/nonessential ingestion; it SHALL return to high only after 15 minutes at or below 85 percent. Where the installed Langfuse edition cannot enforce outcome-specific retention through supported interfaces, the controller SHALL retain all detailed traces for up to 90 days while budgets permit and pause nonessential ingestion before deleting failure evidence or modifying Langfuse-owned schemas.

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

#### Scenario: [GX10-013] Cleanup fails while disk remains high

- **WHEN** supported retention or backup cleanup times out or fails above a watermark
- **THEN** the controller remains in its current high or critical state and emits a correlated alert
- **AND** recovery requires successful cleanup or sustained usage below the matching hysteresis threshold

### Requirement: Production secrets and network boundaries

Secrets SHALL be supplied from OpenBao into runtime-only protected environment files, SHALL never be committed, and SHALL be rotated independently while preserving prior backup decryption recipients for the documented restore window. Stateful services SHALL not be publicly exposed. Langfuse SHALL require authentication, and service-to-service networks SHALL expose only required ports.

External model, transcription, feed, page, video, email, and notification APIs MAY remain reachable through a dedicated Squid 6.13 (`ubuntu/squid:6.13-25.10_beta`) CONNECT proxy whose rendered image SHALL be pinned by immutable digest, with OpenBao credentials, read-only syntax-validated `dstdomain`/CONNECT-port policy, masked host/port/status/timing logs, bounded readiness probes, and DNS-aware hostname/port policy, timeouts, redacted telemetry, and provider-specific rate limits. Application networks SHALL have no direct Internet route; unknown destinations, stale policy, and proxy failure SHALL fail closed. DNS, NTP, certificate-bootstrap, and proxy-health exceptions SHALL be explicit and bounded. Invalid policy/reload, DNS failure, credential failure, proxy outage, and direct-route attempts from every application network SHALL fail closed.

#### Scenario: [GX10-005] External provider call is traced safely

- **WHEN** a local worker calls an allowed external API
- **THEN** the span records provider, operation, duration, status, retry, and bounded usage metadata
- **AND** credentials, authorization headers, raw query secrets, and prohibited payloads are absent

#### Scenario: [GX10-006] Internal port exposure is audited

- **WHEN** deployment validation inspects listening services
- **THEN** PostgreSQL, Redis, Neo4j, ClickHouse, and MinIO data ports are reachable only from approved host or container networks
- **AND** any unexpected public binding fails validation

#### Scenario: [GX10-014] Production secret rotates

- **WHEN** an operator rotates a service credential or backup recipient in OpenBao
- **THEN** affected services reload or restart with the new reference without writing the secret to repository or logs
- **AND** prior backup recipients remain available only for the documented restore window

### Requirement: Backup and restore are operational capabilities

PostgreSQL, Neo4j, ClickHouse, MinIO, and configuration metadata SHALL have scheduled, bounded, correlated backup operations. Backups SHALL be encrypted with an OpenBao-managed age recipient before leaving component-local storage, checksummed, included in the storage budget, and periodically restored into an isolated validation target. Missing encryption material SHALL fail backup activation and SHALL never produce a plaintext artifact. Production acceptance SHALL require application PostgreSQL/queue RPO of at most 24 hours, each component restore RTO of at most 2 hours, and full-stack RTO of at most 4 hours, measured from the declared failure or restore start until a correlated synthetic operation passes.

#### Scenario: [GX10-007] Scheduled backup completes

- **WHEN** the backup schedule runs
- **THEN** each component reports a correlated stage outcome and artifact checksum
- **AND** partial component failure makes the overall backup partial or failed rather than successful

#### Scenario: [GX10-008] Restore drill detects unusable backup

- **WHEN** an isolated restore drill cannot validate application and trace metadata
- **THEN** the drill fails with component-specific diagnostics
- **AND** the source production volumes remain untouched

#### Scenario: [GX10-016] Recovery objectives are exceeded

- **WHEN** an isolated restore drill exceeds the 24-hour application RPO, 2-hour component RTO, or 4-hour full-stack RTO
- **THEN** production recovery acceptance fails with the measured component and full-stack values

#### Scenario: [GX10-015] Backup encryption key is unavailable

- **WHEN** the OpenBao-managed age recipient is missing, invalid, or unreadable
- **THEN** backup activation fails before an artifact leaves component-local storage
- **AND** no plaintext fallback artifact is retained

### Requirement: GX-10 cutover readiness with one ownership authority

The GX-10 SHALL become cutover-ready without receiving production traffic or mutation ownership in this change. Railway and GX-10 MAY coexist for validation, but any later handoff SHALL use one authoritative queue/control PostgreSQL database, a stored ownership epoch, and an authority fingerprint. A process whose configured authority fingerprint or epoch is stale SHALL NOT schedule or claim mutation work. Environment identity, authority fingerprint, and epoch SHALL be present in every operation and trace.

#### Scenario: [GX10-009] GX-10 candidate remains passive

- **WHEN** the GX-10 stack starts before the separate cutover change advances ownership
- **THEN** its schedulers and mutation workers remain passive
- **AND** synthetic verification can run without claiming production work

#### Scenario: [GX10-010] Cutover or rollback authority is invalid

- **WHEN** an operator dry-runs handoff or rollback with independent databases, a stale epoch, or a mismatched authority fingerprint
- **THEN** mutation activation is refused before workers start
- **AND** the refusal and verification are recorded as correlated durable operations

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
