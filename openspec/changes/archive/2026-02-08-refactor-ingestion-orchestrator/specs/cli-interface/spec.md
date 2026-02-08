## MODIFIED Requirements

### Requirement: CLI and API parity
CLI command handlers SHALL call shared orchestrator functions from `src/ingestion/orchestrator.py` for all ingestion operations. API endpoints SHALL enqueue jobs that invoke the same orchestrator functions via the task worker.

#### Scenario: Shared orchestrator functions
- **GIVEN** a CLI command and API-triggered task worker job for the same ingestion source
- **WHEN** both are invoked with equivalent inputs
- **THEN** they SHALL call the same orchestrator function from `src/ingestion/orchestrator.py`
- **AND** the CLI SHALL call the orchestrator function synchronously
- **AND** the task worker SHALL call the orchestrator function via `asyncio.to_thread()`

#### Scenario: Adding a new ingestion source
- **WHEN** a new ingestion source is added to the system
- **THEN** a single orchestrator function SHALL be added to `src/ingestion/orchestrator.py`
- **AND** CLI, pipeline, and task worker SHALL all call that function
- **AND** no ingestion service wiring SHALL be duplicated across call sites

## ADDED Requirements

### Requirement: Ingestion orchestrator module
The system SHALL provide orchestrator functions in `src/ingestion/orchestrator.py` that encapsulate service instantiation and invocation for each ingestion source (gmail, rss, youtube, podcast, substack).

#### Scenario: Orchestrator function contract
- **WHEN** an orchestrator function is called (e.g., `ingest_gmail()`, `ingest_rss()`)
- **THEN** it SHALL import the required service classes lazily (inside the function body)
- **AND** it SHALL instantiate the services, call the appropriate methods, and return `int` (items ingested)
- **AND** source-specific constructor arguments (e.g., `use_oauth`, `session_cookie`) SHALL be accepted as keyword parameters

#### Scenario: YouTube orchestrator encapsulates multi-service pattern
- **WHEN** `ingest_youtube()` is called
- **THEN** it SHALL call `YouTubeContentIngestionService.ingest_all_playlists()`, `YouTubeContentIngestionService.ingest_channels()`, and `YouTubeRSSIngestionService.ingest_all_feeds()`
- **AND** it SHALL return the sum of all three counts

#### Scenario: RSS orchestrator with optional result callback
- **WHEN** `ingest_rss(on_result=callback)` is called
- **THEN** the callback SHALL receive the full `IngestionResult` object (including `failed_sources` and `redirected_sources`)
- **AND** the function SHALL still return `int` (items ingested)
