# Web Search Provider Specification

## Purpose
Unified web search provider abstraction supporting Tavily, Perplexity Sonar, and Grok for ad-hoc search (chat, podcast generation) and scheduled ingestion via `sources.d/websearch.yaml`.

## Requirements

### Requirement: Web Content Ingestion via Perplexity Sonar

The system SHALL support ingestion of AI-relevant web content using the Perplexity Sonar API for broad web search and content discovery.

#### Scenario: Successful web search and ingestion

- **WHEN** the user runs Perplexity search ingestion with a valid API key and search prompt
- **THEN** the system connects to Perplexity Sonar API using the OpenAI SDK with `base_url="https://api.perplexity.ai"`
- **AND** executes search queries with the configured model (default: `sonar`)
- **AND** for each query response, extracts the synthesized content and citation URLs
- **AND** creates one Content record per search response with `source_type=perplexity`
- **AND** generates source_id as `perplexity:{hash(sorted(citations))}` for stable deduplication
- **AND** stores the synthesized answer in markdown_content with numbered citation links
- **AND** stores metadata in metadata_json including citations, search_query, model_used, token_usage
- **AND** returns the count of newly ingested items

#### Scenario: Citation-based deduplication by source_id

- **WHEN** ingesting search results whose citation hash already exists as source_id in the database
- **THEN** the system skips the duplicate without creating new records
- **AND** increments the skipped count in the result

#### Scenario: Citation overlap deduplication

- **WHEN** ingesting search results where >50% of citation URLs already appear in an existing perplexity Content record's metadata_json citations
- **THEN** the system skips the result as a near-duplicate
- **AND** logs a debug message indicating the overlap percentage

#### Scenario: Force reprocessing of existing results

- **WHEN** the user specifies the force reprocess flag
- **THEN** the system updates existing Content records with fresh search data
- **AND** resets the status to PARSED for re-summarization

#### Scenario: API authentication failure

- **WHEN** the Perplexity API key is missing or invalid
- **THEN** the system raises an authentication error with a descriptive message
- **AND** does not create any Content records

#### Scenario: Rate limiting

- **WHEN** the Perplexity API returns a rate limit error
- **THEN** the system implements exponential backoff with retries
- **AND** logs the rate limit event

### Requirement: Configurable Perplexity Search Parameters

The system SHALL support configurable search parameters for controlling Perplexity search behavior and cost.

#### Scenario: Using default search prompt

- **WHEN** no custom prompt is provided
- **THEN** the system uses the prompt from PromptService key `pipeline.perplexity_search.search_prompt`
- **AND** the default prompt focuses on AI research, model releases, and technical developments

#### Scenario: Using custom search prompt

- **WHEN** the user provides a custom search prompt via CLI or API
- **THEN** the system uses the custom prompt for the Perplexity API call
- **AND** stores the search prompt in metadata_json for traceability

#### Scenario: Configuring search context size

- **WHEN** `PERPLEXITY_SEARCH_CONTEXT_SIZE` is set to `low`, `medium`, or `high`
- **THEN** the system passes `web_search_options.search_context_size` to the API
- **AND** `low` reduces cost (~$5/1K requests), `high` increases citation coverage (~$12/1K requests)

#### Scenario: Configuring search recency filter

- **WHEN** `PERPLEXITY_SEARCH_RECENCY_FILTER` is set to `hour`, `day`, `week`, `month`, or `year`
- **THEN** the system passes `search_recency_filter` to the API
- **AND** only content published within the specified timeframe is returned

#### Scenario: Configuring domain filter

- **WHEN** `PERPLEXITY_DOMAIN_FILTER` is configured with domain names
- **THEN** the system passes `search_domain_filter` to the API
- **AND** results are restricted to (or exclude, if prefixed with `-`) the listed domains

### Requirement: Perplexity Search CLI Interface

The system SHALL provide a command-line interface for Perplexity web content ingestion.

#### Scenario: Running from CLI with defaults

- **WHEN** the user runs `aca ingest perplexity-search`
- **THEN** the system executes Perplexity search with default configuration
- **AND** outputs summary statistics on completion (items ingested, skipped, queries made, citations found)

#### Scenario: CLI with custom options

- **WHEN** the user provides CLI options (`--prompt`, `--max-results`, `--force`, `--recency`, `--context-size`)
- **THEN** the system uses the provided options for the ingestion run

#### Scenario: CLI JSON output mode

- **WHEN** the `--json` flag is active
- **THEN** the system outputs structured JSON with source, ingested count, skipped count, queries, citations, and errors

#### Scenario: Pipeline integration

- **WHEN** the daily or weekly pipeline runs
- **AND** `PERPLEXITY_API_KEY` is configured
- **THEN** the system includes Perplexity search as a parallel ingestion source
- **AND** if the API key is not configured, silently skips Perplexity search

### Requirement: Unified Web Search Provider Abstraction

The system SHALL provide a pluggable `WebSearchProvider` protocol used by chat, podcast generation, and digest review for ad-hoc web search. All three providers (Tavily, Perplexity, Grok) SHALL implement this protocol.

#### Scenario: Selecting Tavily as ad-hoc web search provider

- **WHEN** `WEB_SEARCH_PROVIDER` is set to `tavily` (or not set, as default)
- **THEN** ad-hoc web search requests use the Tavily API
- **AND** existing behavior is unchanged
- **AND** the provider's `name` property returns `"tavily"`

#### Scenario: Selecting Perplexity as ad-hoc web search provider

- **WHEN** `WEB_SEARCH_PROVIDER` is set to `perplexity`
- **AND** `PERPLEXITY_API_KEY` is configured
- **THEN** ad-hoc web search requests use the Perplexity Sonar API
- **AND** results include citation URLs in the `WebSearchResult.citations` field
- **AND** `format_results()` includes numbered source links

#### Scenario: Selecting Grok as ad-hoc web search provider

- **WHEN** `WEB_SEARCH_PROVIDER` is set to `grok`
- **AND** `XAI_API_KEY` is configured
- **THEN** ad-hoc web search requests use the xAI Grok API with the `x_search` tool
- **AND** the adapter parses Grok's synthesized response into `WebSearchResult` objects
- **AND** `title` contains the author handle and first line when extractable
- **AND** `url` contains the X.com post URL when extractable, or is empty
- **AND** `content` contains the full synthesized summary

#### Scenario: Web search during podcast script generation

- **WHEN** the podcast script generator calls `_handle_web_search()`
- **THEN** the system delegates to the configured `WebSearchProvider` via `get_web_search_provider()`
- **AND** returns formatted search results regardless of which provider is active

#### Scenario: Web search availability in chat

- **WHEN** the chat configuration endpoint reports `web_search_enabled`
- **THEN** the value is `true` if ANY web search provider's API key is configured (Tavily, Perplexity, or Grok)
- **AND** `false` only if no provider API keys are configured

#### Scenario: Ad-hoc provider not configured

- **WHEN** the selected web search provider's API key is not configured
- **THEN** the system logs a warning
- **AND** returns empty results instead of raising an error

#### Scenario: Formatted results include source attribution

- **WHEN** any `WebSearchProvider` implementation's `format_results()` is called with non-empty results
- **THEN** the output string includes the URL for each result (when available)
- **AND** results are numbered sequentially
- **AND** the format is suitable for LLM context injection (plain text with markdown links)

#### Scenario: Factory with explicit provider override

- **WHEN** a caller requests a specific provider via `get_web_search_provider(provider="perplexity")`
- **THEN** the factory returns that provider regardless of the `WEB_SEARCH_PROVIDER` setting
- **AND** the override is used for sources.d dispatch where each entry specifies its own provider

### Requirement: Scheduled Web Search Sources

The system SHALL support configuring scheduled web searches as ingestion sources via `sources.d/websearch.yaml`.

#### Scenario: Loading websearch source entries

- **WHEN** the pipeline reads `sources.d/websearch.yaml`
- **THEN** the system loads all enabled entries with their provider, prompt, and tags
- **AND** disabled entries are excluded
- **AND** file-level defaults (type, enabled) are applied to entries without explicit values

#### Scenario: Dispatching websearch sources to providers

- **WHEN** the pipeline ingestion stage runs with websearch sources loaded
- **THEN** each source entry is dispatched to the appropriate orchestrator function based on `provider`:
  - `provider: perplexity` → `ingest_perplexity_search(prompt=entry.prompt, ...)`
  - `provider: grok` → `ingest_xsearch(prompt=entry.prompt, ...)`
- **AND** provider-specific options (e.g., `max_threads`, `recency_filter`) are passed through
- **AND** all websearch sources run as parallel tasks

#### Scenario: Websearch source with unconfigured provider

- **WHEN** a websearch source entry specifies a provider whose API key is not configured
- **THEN** the pipeline silently skips that entry
- **AND** other entries with configured providers still execute

#### Scenario: Malformed websearch source entry

- **WHEN** a websearch source entry is missing required fields (`provider` or `prompt`)
- **THEN** the system logs a warning identifying the malformed entry by name or index
- **AND** skips the malformed entry
- **AND** continues processing remaining valid entries

#### Scenario: Unrecognized websearch provider value

- **WHEN** a websearch source entry has a `provider` value other than `perplexity` or `grok`
- **THEN** the system logs a warning with the unrecognized provider name
- **AND** skips the entry
- **AND** continues processing remaining valid entries

#### Scenario: Empty or missing websearch configuration

- **WHEN** `sources.d/websearch.yaml` does not exist or contains no enabled entries
- **THEN** the pipeline continues without web search ingestion
- **AND** existing `aca ingest xsearch` and `aca ingest perplexity-search` CLI commands remain available for manual use
