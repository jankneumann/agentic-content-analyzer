## NEW Capability Spec

This change creates a new capability spec `specs/pipeline/spec.md`.

## ADDED Requirements

### Requirement: Pipeline API endpoint
The system SHALL provide a REST API endpoint for running full pipelines.

#### Scenario: Run daily pipeline
- **WHEN** `POST /api/v1/pipeline/run` is called with `pipeline_type=daily`
- **THEN** a pipeline job SHALL be enqueued to `pgqueuer_jobs`
- **AND** the response SHALL include `job_id` for progress tracking

#### Scenario: Pipeline stages
- **WHEN** a pipeline job is processed by the worker
- **THEN** it SHALL execute stages in order: ingestion → summarization → digest creation
- **AND** each stage transition SHALL update job progress via `update_job_progress()`

#### Scenario: Pipeline progress via SSE
- **WHEN** `GET /api/v1/pipeline/status/{job_id}` is called
- **THEN** a Server-Sent Events stream SHALL report stage-level progress
- **AND** events SHALL include: `stage` (ingestion|summarization|digest), `progress`, `message`

### Requirement: Pipeline CLI via API
The `aca pipeline daily|weekly` commands SHALL call the pipeline API endpoint by default.

#### Scenario: CLI pipeline triggers API
- **WHEN** `aca pipeline daily` is executed in HTTP mode
- **THEN** a `POST /api/v1/pipeline/run` request SHALL be made
- **AND** the CLI SHALL stream progress until completion

#### Scenario: Direct pipeline
- **WHEN** `aca pipeline daily --direct` is executed
- **THEN** the current inline orchestration behavior SHALL be preserved
