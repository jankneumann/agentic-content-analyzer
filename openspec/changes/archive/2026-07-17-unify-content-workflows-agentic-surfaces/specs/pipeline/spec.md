## MODIFIED Requirements

### Requirement: Parallel Source Ingestion

The pipeline SHALL execute all requested registry descriptors with `scheduled=true` concurrently by submitting canonical ingestion commands through `IngestionService`. Source filters MUST be enforced before submission, and no source wiring SHALL exist in pipeline, transport, or worker-specific maps.

#### Scenario: All scheduled sources succeed
- **WHEN** a daily pipeline is submitted without a source filter
- **THEN** all enabled registry sources with `scheduled=true` are submitted concurrently
- **AND** every source result is retained as a canonical ingestion response
- **AND** each source creates an OTel span named `ingestion.{source_key}`

#### Scenario: Partial source failure
- **WHEN** one source fails during parallel ingestion
- **THEN** other independent sources complete successfully
- **AND** the failed child operation and diagnostics are linked to the pipeline operation
- **AND** the configured continuation policy determines whether summarization begins

#### Scenario: Source API rate limit
- **WHEN** a source API returns HTTP 429 during ingestion
- **THEN** the source uses its declared retry policy
- **AND** exhaustion marks only that source child operation failed

#### Scenario: Pipeline and individual ingestion use same service
- **WHEN** a pipeline and an individual ingestion operation run equivalent source commands
- **THEN** both call `IngestionService.execute()` with the same typed command
- **AND** their ingestion response schemas are identical

#### Scenario: Requested source filter is enforced
- **WHEN** a pipeline requests `sources=[rss, readwise]`
- **THEN** only those enabled scheduled descriptors are submitted
- **AND** an unknown or unscheduled source produces a validation problem before the pipeline runs

## ADDED Requirements

### Requirement: Single durable pipeline workflow

CLI, HTTP, MCP, scheduled execution, and frontend pipeline actions SHALL submit one `PipelineWorkflow` operation. The pipeline SHALL represent stages and source work as parent-child PostgreSQL jobs and SHALL return a persisted digest resource on success.

#### Scenario: Equivalent pipeline surfaces converge
- **WHEN** the same normalized pipeline request is submitted through different interfaces
- **THEN** each produces the same parent operation type, stage plan, source commands, and final resource schema

#### Scenario: Pipeline resumes from durable stage state
- **WHEN** a worker restarts after completed child ingestion jobs
- **THEN** the pipeline reuses completed idempotent children
- **AND** it resumes at the first incomplete stage without repeating completed resource creation

### Requirement: Pipeline selection is preserved

The pipeline SHALL resolve one canonical summarized content set after summarization and SHALL pass it unchanged to theme analysis and digest creation.

#### Scenario: Pipeline digest provenance is exact
- **WHEN** a source-filtered pipeline completes
- **THEN** its digest source IDs and count match the pipeline resolved content set
- **AND** theme analysis does not include content from unrequested sources
