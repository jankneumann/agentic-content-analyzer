# llm-provider-routing Specification

## Purpose
TBD - created by archiving change provider-agnostic-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Synchronous LLM generation

`LLMRouter` SHALL provide a `generate_sync()` method with the same interface as `generate()` (model, system_prompt, user_prompt, provider, max_tokens, temperature) that executes synchronously without requiring an async event loop.

#### Scenario: Sync generation with Anthropic provider
- **WHEN** `generate_sync()` is called with a Claude model (e.g., `claude-haiku-4-5`)
- **THEN** the router SHALL resolve the provider to ANTHROPIC (or explicit override)
- **AND** create a sync Anthropic SDK client
- **AND** return an `LLMResponse` with text, input_tokens, output_tokens, provider, and model_version

#### Scenario: Sync generation with Google AI provider
- **WHEN** `generate_sync()` is called with a Gemini model (e.g., `gemini-2.5-flash-lite`)
- **THEN** the router SHALL resolve the provider to GOOGLE_AI
- **AND** create a sync google-genai `Client`
- **AND** return an `LLMResponse` with text and token usage

#### Scenario: Sync generation with OpenAI provider
- **WHEN** `generate_sync()` is called with a GPT model
- **THEN** the router SHALL create a sync `OpenAI` client (not `AsyncOpenAI`)
- **AND** return an `LLMResponse` with text and token usage

#### Scenario: Sync generation records telemetry
- **WHEN** `generate_sync()` completes successfully
- **THEN** the router SHALL call `_trace_llm_call()` with model, provider, prompts, response, and duration
- **AND** telemetry failures SHALL NOT propagate to the caller

### Requirement: Provider resolution from model family

`LLMRouter` SHALL automatically resolve the correct provider for any model based on its model family, without requiring callers to know which SDK to use.

#### Scenario: Gemini model resolves to GOOGLE_AI
- **WHEN** a caller passes `model="gemini-2.5-flash-lite"` without specifying a provider
- **THEN** `resolve_provider()` SHALL return `Provider.GOOGLE_AI`

#### Scenario: Claude model resolves to ANTHROPIC
- **WHEN** a caller passes `model="claude-haiku-4-5"` without specifying a provider
- **THEN** `resolve_provider()` SHALL return `Provider.ANTHROPIC`

#### Scenario: Explicit provider override
- **WHEN** a caller passes `model="claude-sonnet-4-5"` with `provider=Provider.AWS_BEDROCK`
- **THEN** `resolve_provider()` SHALL return `Provider.AWS_BEDROCK`
- **AND** the provider-specific model ID SHALL be used for the API call
