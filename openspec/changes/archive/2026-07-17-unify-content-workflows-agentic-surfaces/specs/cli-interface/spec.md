## MODIFIED Requirements

### Requirement: CLI and API parity

CLI workflow commands and HTTP endpoints SHALL construct the same typed application commands and submit them through the same job-backed application workflow services. Equivalent normalized inputs MUST produce the same operation type, validation behavior, idempotency semantics, and final resource contract.

#### Scenario: Shared job-backed ingestion service
- **GIVEN** a CLI command and HTTP request for the same ingestion source
- **WHEN** both are invoked with equivalent inputs
- **THEN** both submit the same discriminated ingestion command
- **AND** both execute through `IngestionService` in a PostgreSQL worker
- **AND** no source option is lost in either transport
- **AND** URL auto-routing and forced-webpage mode produce equivalent normalized queue payloads

#### Scenario: Adding a new ingestion source
- **WHEN** a new source descriptor and fixture are added
- **THEN** generated CLI and HTTP contracts expose that source
- **AND** no transport-specific dispatcher is added

## REMOVED Requirements

### Requirement: Backward compatibility

Legacy entrypoints SHALL continue to work but emit deprecation warnings.

**Reason**: The coordinated breaking migration removes alternate workflow dispatch and response paths so all interfaces use durable operations and canonical contracts.

**Migration**: Use `aca` canonical source keys and workflow commands documented by `aca capabilities`; update automation to consume `OperationHandle` JSON and use `--wait` when synchronous behavior is required.

#### Scenario: Legacy aliases are removed at cutover
- **WHEN** a removed legacy workflow entrypoint is invoked after cutover
- **THEN** the CLI exits with an unknown-command error
- **AND** help identifies the canonical replacement when a direct mapping exists

## ADDED Requirements

### Requirement: Durable CLI workflow behavior

Every long-running CLI workflow command SHALL submit an operation. Human output SHALL display operation and resource IDs; `--json` SHALL emit the canonical schema; `--wait` SHALL observe the operation until terminal status; and `--no-wait` SHALL return after durable submission.

#### Scenario: CLI waits for digest resource
- **WHEN** `aca digest create ... --wait --json` succeeds
- **THEN** stdout contains the completed operation handle and persisted digest resource reference
- **AND** progress output does not corrupt JSON stdout

#### Scenario: CLI returns queued operation
- **WHEN** a workflow command uses `--no-wait`
- **THEN** it exits successfully after returning a queryable queued operation ID

### Requirement: CLI capability discovery

The CLI SHALL provide `aca capabilities` with human-readable and JSON output derived from the canonical capability document.

#### Scenario: Agent discovers source command fields
- **WHEN** `aca capabilities --json` is executed
- **THEN** the result lists every canonical ingestion discriminator and its accepted fields
- **AND** it lists supported operation and resource types
