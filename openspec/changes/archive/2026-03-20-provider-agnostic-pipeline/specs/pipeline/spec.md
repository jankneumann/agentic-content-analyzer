## MODIFIED Requirements

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

## ADDED Requirements

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
