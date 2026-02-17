## MODIFIED Requirements

### Requirement: Manage subcommands

The system SHALL provide `aca manage` subcommands for setup and operational tasks.

#### Scenario: Setup Gmail OAuth
- **WHEN** `aca manage setup-gmail` is executed
- **THEN** the Gmail OAuth setup flow SHALL be initiated
- **AND** instructions SHALL guide the user through credential creation

#### Scenario: Verify setup
- **WHEN** `aca manage verify-setup` is executed
- **THEN** connectivity checks SHALL run for: database, Redis, Neo4j, LLM API
- **AND** each check SHALL show pass/fail status

#### Scenario: Railway sync
- **WHEN** `aca manage railway-sync` is executed
- **THEN** Railway deployment synchronization SHALL be triggered

#### Scenario: Check profile secrets
- **WHEN** `aca manage check-profile-secrets` is executed
- **THEN** the active profile SHALL be inspected for unresolved `${VAR}` references
- **AND** any missing secrets SHALL be listed as warnings

#### Scenario: Switch embedding provider
- **WHEN** `aca manage switch-embeddings --provider <name> --model <model> [--batch-size N] [--delay N] [--skip-backfill] [--dry-run] [--yes]` is executed
- **THEN** the system validates the target provider/model, clears existing embeddings, rebuilds the HNSW index, and optionally triggers backfill
- **AND** a summary of cleared and regenerated embeddings SHALL be displayed
- **AND** confirmation SHALL be required unless `--yes` is provided

#### Scenario: Backfill chunks
- **WHEN** `aca manage backfill-chunks [--batch-size N] [--delay N] [--dry-run] [--embed-only] [--content-id N]` is executed
- **THEN** existing content without chunks SHALL be chunked and embedded
- **AND** a summary of processed content, created chunks, and generated embeddings SHALL be displayed
