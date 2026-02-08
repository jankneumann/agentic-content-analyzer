## MODIFIED Requirements

### Requirement: Queue-Based Summarization

The pipeline SHALL enqueue content items for summarization and process them via a worker pool. Summarization prompts SHALL be loaded from the `PromptService` (database override, falling back to `prompts.yaml` defaults) rather than from hardcoded string constants.

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
- **WHEN** the Anthropic API returns HTTP 429 during summarization
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

## ADDED Requirements

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
