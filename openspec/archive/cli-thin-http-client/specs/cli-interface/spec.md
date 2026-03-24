## MODIFIED Capability Spec

This change modifies the existing capability spec `specs/cli-interface/spec.md`.

## ADDED Requirements

### Requirement: CLI execution mode
The CLI SHALL support two execution modes: HTTP client mode (default) and direct mode.

#### Scenario: Default HTTP mode
- **WHEN** any `aca` command is executed without `--direct`
- **THEN** the command SHALL attempt to communicate with the backend API via HTTP
- **AND** the API base URL SHALL be read from `Settings.api_base_url`

#### Scenario: Direct mode
- **WHEN** any `aca` command is executed with `--direct`
- **THEN** the command SHALL call orchestrator/service functions directly (current behavior)
- **AND** no HTTP requests SHALL be made to the backend API

#### Scenario: Auto-fallback
- **WHEN** a CLI command attempts HTTP mode but the backend is unreachable
- **THEN** the command SHALL fall back to direct mode automatically
- **AND** a warning SHALL be printed to stderr (unless `--json` is active)

### Requirement: API client configuration
The CLI SHALL read API connection settings from the active profile.

#### Scenario: Local development
- **WHEN** `PROFILE=local` (or no profile set)
- **THEN** `api_base_url` SHALL default to `http://localhost:8000`

#### Scenario: Cloud backend
- **WHEN** `PROFILE=railway`
- **THEN** `api_base_url` SHALL be read from profile settings or `API_BASE_URL` env var

#### Scenario: Authentication
- **WHEN** the CLI makes API requests
- **THEN** the `X-Admin-Key` header SHALL be set from `Settings.admin_api_key`

### Requirement: Job progress display
CLI commands that trigger async jobs SHALL display progress from Server-Sent Events.

#### Scenario: Rich progress (default)
- **WHEN** a job is triggered in HTTP mode without `--json`
- **THEN** a Rich status spinner SHALL display progress messages from SSE events
- **AND** the final result SHALL be displayed when the job completes

#### Scenario: JSON progress
- **WHEN** a job is triggered in HTTP mode with `--json`
- **THEN** only the final job result SHALL be output as JSON to stdout
- **AND** no intermediate progress SHALL be displayed

### Requirement: Ingest commands create tracked jobs
All `aca ingest *` commands in HTTP mode SHALL create entries in the `pgqueuer_jobs` table.

#### Scenario: Gmail ingestion via API
- **WHEN** `aca ingest gmail` is executed in HTTP mode
- **THEN** a `POST /api/v1/contents/ingest` request SHALL be made
- **AND** the response `task_id` SHALL be used to stream progress via SSE
- **AND** a `pgqueuer_jobs` entry with entrypoint `ingest_content` SHALL exist

#### Scenario: All sources supported
- **WHEN** `aca ingest <source>` is executed for any supported source
- **THEN** the source SHALL be passed to the API as the `source` field
- **AND** the API SHALL accept: gmail, rss, youtube, youtube-playlist, youtube-rss, podcast, substack, xsearch, perplexity, url

## MODIFIED Requirements

### Requirement: Ingest subcommands (MODIFIED)
The `aca ingest` subcommands SHALL route through the backend API by default, with `--direct` fallback.

#### Scenario: Ingest Gmail (MODIFIED)
- **WHEN** `aca ingest gmail --max <count>` is executed
- **THEN** a `POST /api/v1/contents/ingest` request SHALL be made with `source=gmail` and `max_results=<count>`
- **AND** if `--max` is not specified, the server SHALL use `sources.d/gmail.yaml` defaults

#### Scenario: Ingest with source-specific options
- **WHEN** `aca ingest xsearch --prompt "..."` is executed
- **THEN** the `prompt` field SHALL be included in the `IngestRequest`
- **AND** source-specific optional fields SHALL be passed through to the API
