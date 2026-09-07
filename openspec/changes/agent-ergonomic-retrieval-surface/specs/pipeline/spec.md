## MODIFIED Requirements

### Requirement: Single durable pipeline workflow

CLI, HTTP, MCP, scheduled execution, and frontend pipeline actions SHALL submit one `PipelineWorkflow` operation. The pipeline SHALL represent stages and source work as parent-child PostgreSQL jobs and SHALL return a persisted digest resource on success. A request with `dry_run = true` SHALL return the plan the workflow would execute without enqueueing any job.

#### Scenario: Equivalent pipeline surfaces converge
- **WHEN** the same normalized pipeline request is submitted through different interfaces
- **THEN** each produces the same parent operation type, stage plan, source commands, and final resource schema

#### Scenario: Pipeline resumes from durable stage state
- **WHEN** a worker restarts after completed child ingestion jobs
- **THEN** the pipeline reuses completed idempotent children
- **AND** it resumes at the first incomplete stage without repeating completed resource creation

#### Scenario: Dry run returns a plan
- **WHEN** a pipeline request is submitted with `dry_run = true` through HTTP, CLI, or MCP
- **THEN** the response is a `PipelinePlan` containing the planned source commands, the ordered child-operation manifest (N `ingestion.execute`, one `summarization.run`, one `digest.create`), the idempotency key a real submission would derive, and `estimated_cost`
- **AND** no `pgqueuer_jobs` row is created
- **AND** the HTTP status is `200`, not `202`

#### Scenario: Dry-run cost estimate declares its basis
- **WHEN** a `PipelinePlan` is returned
- **THEN** `estimated_cost.steps` lists each model-calling step with `model_id`, `provider`, `calls`, and `usd`
- **AND** `estimated_cost.basis` states `content_count`, token averages, and `pricing_source = models.yaml`
- **AND** every `usd` value is computed by `ModelConfig.calculate_cost`

#### Scenario: Dry run with no enabled sources
- **WHEN** the planned source command list is empty
- **THEN** the dry run returns `422` with problem code `pipeline_no_sources`
- **AND** the same request without `dry_run` would have failed the same way
