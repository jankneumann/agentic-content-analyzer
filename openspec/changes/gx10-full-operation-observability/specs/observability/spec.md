## ADDED Requirements

### Requirement: Complete meaningful-operation trace coverage

Langfuse and OpenTelemetry SHALL capture a descriptive root observation for every meaningful operation and nested observations for queue wait, attempt execution, fetch, parse/transcript, filter, model/fallback, persist, index, graph, delivery, maintenance, backup, and alert stages that occur. LLM calls SHALL use generation observations with model, token, usage, latency, and cost metadata.

#### Scenario: [OBS-001] Infrastructure and domain spans remain navigable

- **WHEN** a queued ingestion invokes HTTP, SQL, graph, and model clients
- **THEN** the domain stage hierarchy and relevant infrastructure spans share the operation trace
- **AND** high-volume spans may be filtered only by a documented rule that preserves errors and the parent stage

#### Scenario: [OBS-004] Meaningful entrypoint lacks instrumentation

- **WHEN** the coverage inventory discovers an unallowlisted meaningful entrypoint without operation-context initialization
- **THEN** the trace-coverage gate fails and identifies the entrypoint
- **AND** deployment acceptance cannot report complete coverage

### Requirement: Controlled detail and export-time masking

Detailed traces SHALL include full exception stack evidence, retry/fallback decisions, timings, and explicitly selected bounded input/output excerpts. Automatic capture of arbitrary function arguments, authorization data, secrets, unrestricted URLs, prompts, transcripts, article bodies, or database values SHALL be disabled. A centrally tested export-time masking policy SHALL apply to native Langfuse and third-party OpenTelemetry spans.

#### Scenario: [OBS-002] Secret canary never leaves the process

- **WHEN** a traced operation processes values containing configured secret and PII canaries
- **THEN** exported spans, generations, logs, and PostgreSQL evidence omit or mask those canaries
- **AND** useful operation, stage, provider, model, usage, and diagnostic metadata remains

#### Scenario: [OBS-005] Allowed excerpt remains bounded

- **WHEN** instrumentation selects a non-sensitive input or output excerpt
- **THEN** the exported value is truncated to the configured bound before enqueueing
- **AND** export-time masking still applies to the bounded value

### Requirement: Required trace retention and delivery policy

Production SHALL initially retain complete meaningful-operation traces without sampling while validating the 1 TB storage budget. Any later sampling policy SHALL preserve every failed, partial, security, backup, and telemetry-health operation and SHALL retain durable attempt evidence for unsampled successful work.

Each process SHALL initialize telemetry before instrumented clients, report exporter health, and perform bounded shutdown flush.

#### Scenario: [OBS-003] CLI worker has the same telemetry contract

- **WHEN** a worker starts through the CLI rather than the deployment module
- **THEN** it initializes the same resource identity, masking, propagation, exporter, and shutdown hooks
- **AND** missing required configuration makes readiness visibly degraded

#### Scenario: [OBS-006] Sampling policy would discard failure evidence

- **WHEN** an operator configures sampling that cannot preserve failed, partial, security, backup, and telemetry-health operations
- **THEN** production profile validation rejects the sampling policy
- **AND** unsampled durable attempt evidence remains required for successful work
