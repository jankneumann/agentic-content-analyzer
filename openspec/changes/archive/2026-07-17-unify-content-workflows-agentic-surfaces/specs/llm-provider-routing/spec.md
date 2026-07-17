## ADDED Requirements

### Requirement: Complete pipeline routing through LLMRouter

Summarization, theme analysis, digest generation, podcast script generation, digest revision, podcast revision, and historical-context generation SHALL invoke models through `LLMRouter`. These processors and their transport callers MUST NOT instantiate Anthropic, Gemini, OpenAI, or other provider SDK clients directly.

#### Scenario: Digest generation uses configured non-Anthropic model
- **WHEN** digest generation is configured with a supported non-Anthropic model
- **THEN** every digest LLM call routes through `LLMRouter`
- **AND** provider, token, cost, and telemetry metadata are preserved

#### Scenario: Podcast tool loop is provider neutral
- **WHEN** podcast generation or revision invokes model tools through a supported provider
- **THEN** tool definitions and results use the router's provider-neutral contract
- **AND** the loop does not branch to a provider SDK implementation in the processor

#### Scenario: Direct provider imports fail architecture test
- **WHEN** CI scans pipeline processors and workflow transports
- **THEN** direct provider client imports outside approved provider adapters fail the check
