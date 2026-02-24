# Change: Unified Web Search Provider with Perplexity Integration

## Why

Our content aggregation currently covers email newsletters (Gmail), RSS feeds, YouTube, podcasts, Substack, and X/Twitter (via Grok). However, we miss a large category of signal: **general web content** — blog posts, research announcements, product launches, and technical articles published outside our current source ecosystem. Perplexity's Sonar API provides AI-powered web search with built-in citations, covering hundreds of billions of web pages with semantic understanding.

Additionally, our web search capabilities have grown organically into **three disconnected implementations**:

1. **X-Grok search** (`src/ingestion/xsearch.py`): Full ingestion service for X/Twitter content, but can't be used for ad-hoc search during chat/review
2. **Tavily** (`src/services/tavily_service.py`): Simple tool wrapper for ad-hoc search in chat and podcast generation, but can't ingest content
3. **Perplexity** (new): Could serve both roles, but adding it as yet another one-off would deepen the fragmentation

This proposal addresses both problems:

1. **Unified Web Search Provider abstraction**: Move Tavily, Perplexity, and Grok behind a `WebSearchProvider` protocol so all three can serve as both **ad-hoc search tools** (chat, digest review, podcast script generation) and **scheduled ingestion sources** (daily/weekly content discovery).
2. **Perplexity integration**: Add Perplexity Sonar API as a new provider — filling the gap for general web content that's not social media (Grok's strength) or newsletter-specific (RSS/Gmail/Substack).
3. **Scheduled web search sources**: Introduce `sources.d/websearch.yaml` configuration so users can define multiple search prompts with specific providers, replacing external prompt workflows with in-app scheduled ingestion.

> **Note**: "Web search" in this proposal refers to **external web search providers** (Tavily, Perplexity, Grok) used for content discovery. This is distinct from the existing **document search** system (`HybridSearchService`) which provides internal BM25+vector search over already-ingested content.

## What Changes

### Web Search Provider Abstraction (unification layer)
- Create `WebSearchProvider` protocol in `src/services/web_search.py` with `search()` and `format_results()` methods
- Create `WebSearchResult` dataclass as the common result type across all providers
- Adapt existing `TavilyService` to implement `WebSearchProvider` (wrapper, no behavioral changes)
- Create `PerplexitySearchService` implementing `WebSearchProvider` for ad-hoc search
- Create `GrokSearchService` implementing `WebSearchProvider` for ad-hoc search (adapts `GrokXClient.search()` to return `WebSearchResult` objects)
- Add `WEB_SEARCH_PROVIDER` setting with values: `tavily` (default), `perplexity`, `grok`
- Add `get_web_search_provider()` factory function for consumer code
- Wire into podcast script generator's `_handle_web_search` via the provider abstraction
- Update chat routes `web_search_enabled` to check any configured web search provider (not just Tavily)

### Perplexity Ingestion (new content source)
- Add `ContentSource.PERPLEXITY = "perplexity"` to the content source enum
- Create `PerplexityClient` using the OpenAI SDK with `base_url="https://api.perplexity.ai"` (no new SDK dependency)
- Create `PerplexityContentIngestionService` following the Client-Service pattern from xSearch
- Add `aca ingest perplexity-search` CLI command with `--prompt`, `--max-results`, `--force` options
- Add orchestrator function `ingest_perplexity_search()` with `on_result` callback
- Add configurable search prompt via `pipeline.perplexity_search.search_prompt` in PromptService
- Store discovered articles as Content records with citation URLs, source metadata, and search context
- Include in daily/weekly pipeline alongside other ingestion sources

### Scheduled Web Search Sources (sources.d configuration)
- Add `sources.d/websearch.yaml` configuration file for defining scheduled search sources
- Each entry specifies: `name`, `provider` (grok/perplexity), `prompt`, `enabled`, `tags`
- Pipeline reads websearch sources and dispatches to the appropriate provider's ingestion service
- Replaces manual 2-prompt external workflow with in-app scheduled ingestion
- X-Grok's existing prompt-based ingestion (`aca ingest xsearch --prompt`) becomes one source entry alongside Perplexity entries
- **Migrate xsearch out of hardcoded pipeline**: Remove the hardcoded `ingest_xsearch` from `_run_ingestion_stage_async()` — X search is now driven exclusively by `sources.d/websearch.yaml` entries. This prevents double-execution. The `aca ingest xsearch` CLI command remains for manual use.

## Capabilities

### New Capabilities
- `web-search-provider`: Unified web search abstraction for ad-hoc and ingestion use cases across Tavily, Perplexity, and Grok

### Modified Capabilities
- `content-ingestion`: Add perplexity as a new ingestion source
- `source-configuration`: Add `websearch.yaml` source type for scheduled search sources
- `pipeline`: Include web search sources in daily/weekly pipeline
- `cli-interface`: Add `aca ingest perplexity-search` command

## Impact

- **Affected code**:
  - `src/models/content.py`: Add `ContentSource.PERPLEXITY` enum value
  - `src/ingestion/perplexity_search.py`: New module with Perplexity client and ingestion service
  - `src/services/web_search.py`: New web search provider abstraction (protocol, factory, result types)
  - `src/services/tavily_service.py`: Adapt to implement `WebSearchProvider` protocol
  - `src/ingestion/xsearch.py`: Extract ad-hoc search adapter from `GrokXClient`
  - `src/ingestion/orchestrator.py`: Add `ingest_perplexity_search()`, update `ingest_xsearch()` to support sources.d
  - `src/cli/ingest_commands.py`: Add `aca ingest perplexity-search` CLI command
  - `src/cli/pipeline_commands.py`: Add perplexity to pipeline, read websearch.yaml sources
  - `src/api/chat_routes.py`: Update `web_search_enabled` to check any configured provider
  - `src/config/settings.py`: Add Perplexity settings, `web_search_provider` setting
  - `src/config/prompts.yaml`: Add default Perplexity search prompt
  - `src/config/source_loader.py`: Support `websearch` source type
  - `src/processors/podcast_script_generator.py`: Use web search provider abstraction
  - `sources.d/websearch.yaml`: New source configuration file
  - `alembic/`: Migration to add `perplexity` enum value
- **New dependencies**: None (uses existing `openai` SDK with base_url override)
- **Cost**: Perplexity Sonar at medium context: ~$0.008/request + tokens. ~$0.10-0.20/day for 10-20 daily queries. Grok X search: $5/1K tool calls. Both configurable via max_results/max_threads limits.
- **No breaking changes**: Additive feature. Tavily remains the default ad-hoc web search provider. Existing `aca ingest xsearch` CLI command continues to work unchanged.
