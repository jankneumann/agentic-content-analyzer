# pipeline Specification

## Purpose
TBD - created by archiving change add-parallel-job-queue. Update Purpose after archive.
## Requirements
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

### Requirement: Queue-Based Summarization

The pipeline SHALL enqueue content items for summarization and process them via a worker pool. Summarization prompts SHALL be loaded from the `PromptService` (database override, falling back to `prompts.yaml` defaults) rather than from hardcoded string constants. The summarization agent SHALL route LLM calls through `LLMRouter` to support any configured provider.

#### Scenario: Batch summarization via queue
- **WHEN** `aca summarize pending` is executed
- **THEN** pending content IDs are enqueued to `pgqueuer_jobs` with entrypoint `summarize_content`
- **AND** each job payload MUST include `{"content_id": int}`
- **AND** workers process items concurrently up to the concurrency limit
- **AND** progress is tracked in `pgqueuer_jobs.payload.progress` (0-100)

#### Scenario: Worker concurrency limit
- **WHEN** a worker pool starts with `--concurrency 5`
- **THEN** the number of jobs in `in_progress` status is <= 5 at all times
- **AND** when the 6th job is enqueued, it remains in `queued` status until a running job completes

#### Scenario: LLM rate limit during summarization
- **WHEN** any LLM provider API returns HTTP 429 during summarization
- **THEN** the worker retries with exponential backoff (5s, 10s, 20s, max 3 retries)
- **AND** if all retries fail, the job is marked `failed` with error `rate_limit_exceeded`
- **AND** the worker continues processing other jobs

#### Scenario: Idempotent job enqueueing
- **WHEN** `aca summarize pending` is called while jobs for the same content_ids are already queued
- **THEN** duplicate jobs are NOT created
- **AND** only content_ids not already in `queued` or `in_progress` status are enqueued

#### Scenario: Summarization uses configurable prompts
- **WHEN** a content item is summarized
- **THEN** the summarization agent SHALL load the system prompt via `PromptService.get_pipeline_prompt("summarization", "system")`
- **AND** the user prompt template SHALL be loaded via `PromptService.get_pipeline_prompt("summarization", "user_template")`
- **AND** template variables (`{title}`, `{publication}`, `{author}`, `{date}`, `{source_type}`, `{content}`) SHALL be interpolated at runtime
- **AND** if a database override exists for the prompt key, the override SHALL be used instead of the YAML default

#### Scenario: Summarization with non-Anthropic model
- **WHEN** `MODEL_SUMMARIZATION` is set to a non-Anthropic model (e.g., `gemini-2.5-flash-lite`)
- **AND** the corresponding provider API key is configured (e.g., `GOOGLE_API_KEY`)
- **THEN** the summarization agent SHALL route the LLM call through `LLMRouter.generate_sync()`
- **AND** `LLMRouter` SHALL resolve the provider from the model family (e.g., GOOGLE_AI for Gemini)
- **AND** the summarization SHALL complete successfully with the non-Anthropic model
- **AND** cost tracking SHALL use the correct per-provider pricing

#### Scenario: Summarization provider failover
- **WHEN** the primary provider for a model fails (e.g., API error)
- **AND** a fallback provider is configured for the same model
- **THEN** `LLMRouter` SHALL retry with the fallback provider
- **AND** the successful provider SHALL be recorded in the summary metadata

### Requirement: Pipeline Progress Tracking

The pipeline SHALL emit structured progress events for each stage.

#### Scenario: Stage progress via OTel spans
- **WHEN** the `aca pipeline daily` command is executed
- **THEN** each stage creates an OTel span named `pipeline.{stage}` (e.g., `pipeline.ingestion`, `pipeline.summarization`, `pipeline.digest`)
- **AND** each span MUST include attributes: `status` (success|failure|partial), `item_count` (integer)
- **AND** failure spans MUST include `error_message` attribute

#### Scenario: Resumable pipeline after crash
- **WHEN** the pipeline process is interrupted mid-summarization (SIGTERM or crash)
- **AND** the pipeline command is restarted
- **THEN** only jobs with status `queued` or `in_progress` (updated_at < 1 hour ago) are processed
- **AND** jobs with status `completed` are skipped
- **AND** stale `in_progress` jobs (updated_at >= 1 hour ago) are marked `failed` with error `stale_timeout`

#### Scenario: Pipeline timeout
- **WHEN** the pipeline has been running for more than `PIPELINE_TIMEOUT` (default: 2 hours)
- **THEN** the pipeline logs a warning and continues (does not force-terminate)
- **AND** individual job timeouts are handled separately by workers

### Requirement: Configurable Pipeline Prompts

All pipeline processors SHALL load their LLM prompts via `PromptService` instead of using hardcoded string constants. Each processor SHALL support database overrides that take precedence over `prompts.yaml` defaults.

#### Scenario: Digest creation uses configurable prompt
- **WHEN** a digest is created
- **THEN** the system prompt SHALL be loaded via `PromptService.get_pipeline_prompt("digest_creation", "system")`
- **AND** if a database override exists for key `pipeline.digest_creation.system`, the override SHALL be used

#### Scenario: Theme analysis uses configurable prompt
- **WHEN** theme analysis is performed
- **THEN** the system prompt SHALL be loaded via `PromptService.get_pipeline_prompt("theme_analysis", "system")`
- **AND** if a database override exists for key `pipeline.theme_analysis.system`, the override SHALL be used

#### Scenario: Podcast script generation uses configurable prompts
- **WHEN** a podcast script is generated
- **THEN** the system prompt SHALL be loaded via `PromptService.get_pipeline_prompt("podcast_script", "system")`
- **AND** length-specific prompts SHALL be loaded via `PromptService.get_pipeline_prompt("podcast_script", "length_{length}")`
- **AND** template variables (`{period}`, `{word_count_min}`, `{word_count_max}`, `{duration_mins}`) SHALL be interpolated

#### Scenario: Digest revision uses configurable prompt
- **WHEN** a digest revision is requested
- **THEN** the system prompt SHALL be loaded via `PromptService.get_pipeline_prompt("digest_revision", "system")`

#### Scenario: Script revision uses configurable prompt
- **WHEN** a podcast script section revision is requested
- **THEN** the system prompt SHALL be loaded via `PromptService.get_pipeline_prompt("script_revision", "system")`

#### Scenario: Historical context uses configurable prompt
- **WHEN** theme evolution analysis is performed
- **THEN** the prompt template SHALL be loaded via `PromptService.get_pipeline_prompt("historical_context", "evolution_template")`

#### Scenario: Prompt override applied at runtime
- **WHEN** a user has set a custom prompt override via the settings API or CLI
- **AND** a pipeline processor runs
- **THEN** the processor SHALL use the overridden prompt value
- **AND** the `prompts.yaml` default SHALL NOT be used for that key

#### Scenario: Fallback to YAML when no DB available
- **WHEN** a processor runs without a database session
- **THEN** prompts SHALL be loaded from `prompts.yaml` defaults
- **AND** the processor SHALL function correctly without database access

### Requirement: Theme analysis persists results
The pipeline's theme analysis step SHALL persist analysis results to the PostgreSQL database and write a summary episode to the Neo4j knowledge graph, rather than storing results in ephemeral in-memory dicts.

#### Scenario: Pipeline theme analysis creates DB record
- **WHEN** `aca analyze themes` completes successfully
- **THEN** a `ThemeAnalysis` record SHALL exist in the database with `status=completed`

#### Scenario: Pipeline theme analysis writes to Neo4j
- **WHEN** `aca analyze themes` completes successfully
- **THEN** a Graphiti episode containing the theme analysis summary SHALL be added to the knowledge graph

### Requirement: Provider-agnostic digest revision

The digest revision processor SHALL route LLM calls through `LLMRouter` to support any configured provider, not just Anthropic.

#### Scenario: Digest revision with non-Anthropic model
- **WHEN** `MODEL_DIGEST_REVISION` is set to a non-Anthropic model (e.g., `gemini-2.5-flash`)
- **AND** the corresponding provider API key is configured
- **THEN** `DigestReviser.revise_section()` SHALL route the LLM call through `LLMRouter.generate_with_tools()`
- **AND** tool definitions (`fetch_content`, `search_content`) SHALL be converted to provider-agnostic `ToolDefinition` objects
- **AND** the agentic tool-use loop SHALL work with any supported provider

#### Scenario: Digest revision tool use with Gemini
- **WHEN** the revision model is a Gemini model
- **AND** the LLM requests the `fetch_content` tool during revision
- **THEN** `LLMRouter` SHALL convert tool calls to the Gemini function-calling format
- **AND** tool results SHALL be passed back in Gemini's `Part.from_function_response()` format
- **AND** the revision loop SHALL continue until the model produces a final text response

#### Scenario: Digest revision tool use with OpenAI
- **WHEN** the revision model is an OpenAI model
- **AND** the LLM requests the `search_content` tool during revision
- **THEN** `LLMRouter` SHALL convert tool calls to OpenAI's function-calling format
- **AND** tool results SHALL be passed back with the correct `tool_call_id`
- **AND** the revision loop SHALL continue until the model produces a final text response

#### Scenario: Backward-compatible digest revision
- **WHEN** `MODEL_DIGEST_REVISION` is set to a Claude model (default)
- **THEN** digest revision SHALL behave identically to the current Anthropic-only implementation
- **AND** token usage, cost tracking, and telemetry SHALL be preserved

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
