# developer-workflow Specification

## Purpose
TBD - created by archiving change add-profile-make-targets. Update Purpose after archive.
## Requirements
### Requirement: Profile-Based Make Targets

The system SHALL provide make targets that set the `PROFILE` environment variable and run development commands.

#### Scenario: Start local development without observability
- **GIVEN** the developer runs `make dev-local`
- **WHEN** the command completes
- **THEN** the backend API SHALL start with `PROFILE=local`
- **AND** observability SHALL be disabled (noop provider)

#### Scenario: Start local development with Opik observability
- **GIVEN** Opik stack is running (accessible at http://localhost:5174)
- **AND** the developer runs `make dev-opik`
- **WHEN** the command completes
- **THEN** the backend API SHALL start with `PROFILE=local-opik`
- **AND** LLM traces SHALL be exported to Opik

#### Scenario: Opik not running error
- **GIVEN** Opik stack is NOT running
- **WHEN** the developer runs `make dev-opik`
- **THEN** the command SHALL fail with an error message
- **AND** the message SHALL instruct to run `make opik-up` first

### Requirement: Opik Stack Management

The system SHALL provide make targets to manage the Opik self-hosted observability stack.

#### Scenario: Start Opik stack
- **GIVEN** Docker is running
- **WHEN** the developer runs `make opik-up`
- **THEN** the Opik stack SHALL start via `docker compose -f docker-compose.opik.yml -p opik up -d`
- **AND** the command SHALL wait until Opik backend health check passes
- **AND** a success message SHALL indicate Opik is ready at http://localhost:5174

#### Scenario: Stop Opik stack
- **GIVEN** Opik stack is running
- **WHEN** the developer runs `make opik-down`
- **THEN** the Opik stack SHALL stop via `docker compose -f docker-compose.opik.yml -p opik down`

#### Scenario: View Opik logs
- **GIVEN** Opik stack is running
- **WHEN** the developer runs `make opik-logs`
- **THEN** logs from all Opik services SHALL be displayed

### Requirement: Full Stack Management

The system SHALL provide make targets to manage both core services and Opik together.

#### Scenario: Start full stack
- **GIVEN** Docker is running
- **WHEN** the developer runs `make full-up`
- **THEN** core services (postgres, redis, neo4j) SHALL start
- **AND** Opik stack SHALL start
- **AND** both stacks SHALL be healthy before command completes

#### Scenario: Stop full stack
- **GIVEN** both stacks are running
- **WHEN** the developer runs `make full-down`
- **THEN** Opik stack SHALL stop first
- **AND** core services SHALL stop second

### Requirement: Profile Verification

The system SHALL provide make targets to verify profile configuration works end-to-end.

#### Scenario: Verify current profile
- **GIVEN** the API is running
- **WHEN** the developer runs `make verify-profile`
- **THEN** API health check SHALL be performed
- **AND** API readiness (database connection) SHALL be verified
- **AND** current profile SHALL be validated via CLI

#### Scenario: Verify Opik tracing
- **GIVEN** Opik is running and `PROFILE=local-opik`
- **WHEN** the developer runs `make verify-opik`
- **THEN** a test trace SHALL be sent to Opik
- **AND** success message SHALL indicate trace was sent
- **AND** message SHALL include Opik UI URL to view trace

### Requirement: Opik Port Assignment

The Opik stack SHALL use port 5174 for the frontend UI to avoid conflict with Vite dev server (port 5173).

#### Scenario: No port conflict with Vite
- **GIVEN** Opik stack is running on port 5174
- **AND** Vite dev server is running on port 5173
- **WHEN** both services are accessed
- **THEN** Opik UI SHALL be accessible at http://localhost:5174
- **AND** Vite dev server SHALL be accessible at http://localhost:5173
- **AND** no port binding errors SHALL occur

### Requirement: local-opik Profile

The system SHALL provide a `local-opik` profile that extends `local` with Opik observability enabled.

#### Scenario: Profile inheritance
- **GIVEN** `profiles/local-opik.yaml` exists
- **WHEN** the profile is loaded
- **THEN** it SHALL inherit all settings from `local` profile
- **AND** `providers.observability` SHALL be `opik`
- **AND** `otel_exporter_otlp_endpoint` SHALL point to local Opik instance

#### Scenario: Profile validation
- **GIVEN** Opik is NOT running
- **WHEN** `python -m src.cli profile validate local-opik` is run
- **THEN** validation SHALL pass (endpoint is syntactically valid)
- **AND** a warning MAY be shown that endpoint is not reachable
