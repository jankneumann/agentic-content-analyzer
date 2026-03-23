## NEW Capability Spec

This change creates a new capability spec `specs/content-ingestion/spec.md`.

## ADDED Requirements

### Requirement: Source configuration defaults
The ingestion orchestrator SHALL read defaults from `sources.d/*.yaml` when parameters are not explicitly provided.

#### Scenario: Gmail uses source config defaults
- **WHEN** `ingest_gmail()` is called without `max_results`
- **THEN** the orchestrator SHALL read `sources.d/gmail.yaml` via `get_gmail_sources()`
- **AND** use the first source's `max_results` and `query` values as defaults

#### Scenario: Explicit parameters override config
- **WHEN** `ingest_gmail(max_results=20)` is called with an explicit value
- **THEN** the explicit value SHALL take precedence over `sources.d/gmail.yaml`

### Requirement: Extended ingestion API
The `POST /api/v1/contents/ingest` endpoint SHALL accept all source types and source-specific parameters.

#### Scenario: X search ingestion
- **WHEN** `source=xsearch` with `prompt` field is submitted
- **THEN** the worker SHALL call `ingest_xsearch()` with the provided prompt

#### Scenario: Perplexity search ingestion
- **WHEN** `source=perplexity` with `prompt`, `recency_filter`, `context_size` fields is submitted
- **THEN** the worker SHALL call `ingest_perplexity_search()` with all provided parameters

#### Scenario: URL ingestion
- **WHEN** `source=url` with `url` field is submitted
- **THEN** the worker SHALL call `ingest_url()` with URL, title, tags, and notes

#### Scenario: Server-side defaults
- **WHEN** `max_results` is null in the IngestRequest
- **THEN** the worker SHALL pass `None` to the orchestrator
- **AND** the orchestrator SHALL apply `sources.d/*.yaml` defaults
