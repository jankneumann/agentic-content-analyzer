## MODIFIED Requirements

### Requirement: Parallel Source Ingestion

The pipeline SHALL execute all ingestion sources (Gmail, RSS, YouTube, Podcast, Substack) concurrently by calling shared orchestrator functions from `src/ingestion/orchestrator.py` via `asyncio.to_thread()`.

#### Scenario: All sources succeed
- **WHEN** the `aca pipeline daily` command is executed
- **THEN** all ingestion sources are fetched concurrently via `asyncio.gather()` calling orchestrator functions
- **AND** total ingestion time equals the slowest source (not sum of all)
- **AND** each source creates an OTel span named `ingestion.{source_name}`

#### Scenario: Partial source failure
- **WHEN** one source fails during parallel ingestion (e.g., Gmail API returns 401)
- **THEN** other independent sources complete successfully
- **AND** the failed source creates an OTel span with `status=ERROR` including: source_name, error_type, error_message
- **AND** the pipeline continues to summarization if at least 1 source returned content
- **AND** the pipeline exits with code 0 (partial failure is not fatal)

#### Scenario: Source API rate limit
- **WHEN** a source API returns HTTP 429 (rate limited) during parallel ingestion
- **THEN** the source retries with exponential backoff (1s, 2s, 4s, max 3 retries)
- **AND** if all retries fail, the source is marked failed and other sources continue

#### Scenario: Pipeline and task worker use same orchestrator
- **WHEN** the pipeline ingests from a source
- **AND** the task worker processes an `ingest_content` job for the same source
- **THEN** both SHALL call the same orchestrator function from `src/ingestion/orchestrator.py`
- **AND** no ingestion service wiring SHALL exist outside the orchestrator module
