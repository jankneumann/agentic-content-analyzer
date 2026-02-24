# Tasks: Unified Web Search Provider with Perplexity Integration

> **Dependency notation**: `[depends: X.Y]` means this task depends on task X.Y completing first.
> Tasks without dependency annotations are independent and can be parallelized.

## 1. WebSearchProvider Protocol and Factory

> Independent — no dependencies. This is the foundation that all provider adapters build on.

- [ ] 1.1 Create `src/services/web_search.py` with provider protocol and types:
  ```python
  @dataclass
  class WebSearchResult:
      title: str
      url: str
      content: str
      score: float | None = None
      citations: list[str] | None = None
      metadata: dict[str, Any] | None = None

  @runtime_checkable
  class WebSearchProvider(Protocol):
      @property
      def name(self) -> str: ...
      def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]: ...
      def format_results(self, results: list[WebSearchResult]) -> str: ...

  def get_web_search_provider(provider: str | None = None) -> WebSearchProvider:
      """Factory. Uses settings.web_search_provider if provider not specified."""
  ```
- [ ] 1.2 Add `web_search_provider: str = "tavily"` to `src/config/settings.py` (env: `WEB_SEARCH_PROVIDER`, values: `tavily|perplexity|grok`)

## 2. Tavily WebSearchProvider Adapter

> `[depends: 1.1]` — needs the protocol definition.
> **File scope**: `src/services/tavily_service.py`, `src/services/web_search.py`

- [ ] 2.1 Create `TavilyWebSearchProvider` class implementing `WebSearchProvider`:
  - Wraps existing `TavilyService.search()` return in `WebSearchResult` dataclass
  - `name` property returns `"tavily"`
  - `format_results()` delegates to existing `TavilyService.format_results()`
  - No behavioral changes — interface alignment only
- [ ] 2.2 Register `TavilyWebSearchProvider` in `get_web_search_provider()` factory for `provider="tavily"`

## 3. Configuration and Settings (Perplexity)

> Independent — no dependencies. Parallel with tasks 1 and 2.

- [ ] 3.1 Add Perplexity configuration settings to `src/config/settings.py`:
  - `perplexity_api_key: str | None = None` (env: `PERPLEXITY_API_KEY`)
  - `perplexity_model: str = "sonar"` (env: `PERPLEXITY_MODEL`)
  - `perplexity_search_context_size: str = "medium"` (env: `PERPLEXITY_SEARCH_CONTEXT_SIZE`)
  - `perplexity_search_recency_filter: str = "week"` (env: `PERPLEXITY_SEARCH_RECENCY_FILTER`)
  - `perplexity_max_results: int = 30` (env: `PERPLEXITY_MAX_RESULTS`)
  - `perplexity_domain_filter: list[str] = []` (env: `PERPLEXITY_DOMAIN_FILTER`)
- [ ] 3.2 Add settings to `profiles/base.yaml` with `${PERPLEXITY_API_KEY:-}` interpolation
- [ ] 3.3 Document environment variables in CLAUDE.md

## 4. Database Schema

> Independent — no dependencies. Parallel with tasks 1-3.

- [ ] 4.1 Add `PERPLEXITY = "perplexity"` to `ContentSource` enum in `src/models/content.py`
- [ ] 4.2 Create Alembic migration to add `perplexity` value to `content_source` enum type:
  ```sql
  ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'perplexity';
  ```
- [ ] 4.3 Run migration locally and verify enum update

## 5. Perplexity Client and Data Models

> `[depends: 3.1]` — needs settings fields for API key and model config.
> **File scope**: `src/ingestion/perplexity_search.py`

- [ ] 5.1 Create `src/ingestion/perplexity_search.py` module with data models:
  ```python
  @dataclass
  class PerplexitySearchResult:
      items_ingested: int = 0
      items_skipped: int = 0
      queries_made: int = 0
      citations_found: int = 0
      errors: list[str] = field(default_factory=list)
  ```
- [ ] 5.2 Implement `PerplexityClient` class:
  ```python
  class PerplexityClient:
      def __init__(self, api_key: str | None = None, model: str = "sonar")
      def search(self, prompt: str, system_prompt: str | None = None,
                 recency_filter: str = "week",
                 domain_filter: list[str] | None = None,
                 search_context_size: str = "medium") -> PerplexityResponse
      def close(self) -> None
  ```
  - Use `openai.OpenAI(api_key=key, base_url="https://api.perplexity.ai")`
  - Pass Perplexity-specific params via `extra_body`
  - Parse `citations` array from response
- [ ] 5.3 Implement `PerplexityResponse` Pydantic model:
  ```python
  class PerplexityResponse(BaseModel):
      content: str
      citations: list[str] = []
      related_questions: list[str] = []
      model: str = ""
      usage: dict[str, int] = {}
  ```
- [ ] 5.4 Implement response-to-ContentData conversion:
  - Format citations as numbered markdown links
  - Generate `source_id` as `perplexity:{hash(sorted(citations))}`
  - Store full metadata including search params, citations, token usage
- [ ] 5.5 Add error handling for API failures, auth errors, rate limits
- [ ] 5.6 Add retry logic with exponential backoff for transient errors

## 6. Perplexity Ingestion Service

> `[depends: 4.1, 5.2]` — needs ContentSource enum value and PerplexityClient.
> **File scope**: `src/ingestion/perplexity_search.py`

- [ ] 6.1 Implement `PerplexityContentIngestionService`:
  ```python
  class PerplexityContentIngestionService:
      def __init__(self)
      def ingest_content(
          self,
          prompt: str | None = None,
          max_results: int | None = None,
          force_reprocess: bool = False,
      ) -> PerplexitySearchResult
      def close(self) -> None
  ```
- [ ] 6.2 Implement prompt retrieval via `PromptService`:
  - Key: `pipeline.perplexity_search.search_prompt`
  - Fallback to settings/default if not overridden
- [ ] 6.3 Implement citation-based deduplication:
  - Primary: `source_id` match (hash of sorted citation URLs)
  - Secondary: >50% citation URL overlap with existing perplexity Content
  - Fallback: content hash
- [ ] 6.4 Use SAVEPOINT isolation per search result (same pattern as xSearch)
- [ ] 6.5 Track cost metadata: token usage, request count, context size

## 7. Default Search Prompt

> Independent — no dependencies. Parallel with other tasks.

- [ ] 7.1 Add default search prompt to `src/config/prompts.yaml`:
  ```yaml
  pipeline.perplexity_search.search_prompt:
    category: pipeline
    description: Default prompt for Perplexity AI news web search
    template: |
      Search for the latest AI and technology news from the past week. Focus on:
      - New model releases and capabilities from major AI labs
      - Research paper announcements with links to papers or blog posts
      - Technical deep dives on LLMs, RAG, AI agents, and machine learning engineering
      - AI startup funding rounds, acquisitions, and partnerships
      - Developer tool releases, framework updates, and infrastructure changes
      - Industry analysis and trend reports from reputable sources

      Return comprehensive coverage with detailed summaries and always cite your sources.
      Prioritize content from established tech publications, company blogs, and research institutions.
  ```

## 8. Perplexity WebSearchProvider Adapter

> `[depends: 1.1, 5.2]` — needs the protocol definition and PerplexityClient.
> **File scope**: `src/services/web_search.py`

- [ ] 8.1 Create `PerplexityWebSearchProvider` implementing `WebSearchProvider`:
  - Uses `PerplexityClient` for API calls
  - Maps Perplexity citations to `WebSearchResult` objects with `citations` field
  - `format_results()` includes numbered citation URLs
  - `name` property returns `"perplexity"`
- [ ] 8.2 Register in `get_web_search_provider()` factory for `provider="perplexity"`

## 9. Grok WebSearchProvider Adapter

> `[depends: 1.1]` — needs the protocol definition. Does NOT modify xsearch.py internals.
> **File scope**: `src/services/web_search.py` (or `src/services/grok_search_adapter.py`)

- [ ] 9.1 Create `GrokWebSearchProvider` implementing `WebSearchProvider`:
  - Instantiates `GrokXClient` internally
  - `search()` calls `GrokXClient.search(prompt=query)` to get synthesized text
  - Parses response to extract individual thread/post references
  - Maps each to `WebSearchResult`:
    - `title`: `"{author_handle}: {first_line}"` (if extractable) or query text
    - `url`: `"https://x.com/{handle}/status/{post_id}"` (if extractable, else empty)
    - `content`: synthesized summary
    - `metadata`: `{"source": "x.com", "author": "...", ...}`
  - Limits output to `max_results`
  - `name` property returns `"grok"`
- [ ] 9.2 Register in `get_web_search_provider()` factory for `provider="grok"`

## 10. Orchestrator Integration

> `[depends: 6.1]` — needs PerplexityContentIngestionService.
> **File scope**: `src/ingestion/orchestrator.py`

- [ ] 10.1 Add `ingest_perplexity_search()` to `src/ingestion/orchestrator.py`:
  ```python
  def ingest_perplexity_search(
      *,
      prompt: str | None = None,
      max_results: int | None = None,
      force_reprocess: bool = False,
      on_result: Callable[[PerplexitySearchResult], None] | None = None,
  ) -> int:
  ```
  - Lazy import service
  - Delegate to `service.ingest_content()`
  - Pass `on_result` callback for CLI reporting
  - Ensure `service.close()` in try/finally
  - Return `result.items_ingested`

## 11. CLI Command

> `[depends: 10.1]` — needs orchestrator function.
> **File scope**: `src/cli/ingest_commands.py`

- [ ] 11.1 Add `aca ingest perplexity-search` command to `src/cli/ingest_commands.py`:
  - `--prompt, -p`: Override default search prompt
  - `--max-results, -m`: Limit number of results
  - `--force, -f`: Force reprocess duplicates
  - `--recency`: Override recency filter (hour/day/week/month)
  - `--context-size`: Override search context size (low/medium/high)
- [ ] 11.2 Implement human-readable output:
  - Show items ingested, skipped, queries made, citations found
  - Show errors if any
- [ ] 11.3 Implement JSON output mode via `is_json_mode()` guard pattern
- [ ] 11.4 Implement `on_result` callback to capture `PerplexitySearchResult`

## 12. Wire WebSearchProvider into Consumers

> `[depends: 2.1, 8.1, 9.1]` — needs all three provider adapters registered.
> **File scope**: `src/processors/podcast_script_generator.py`, `src/api/chat_routes.py`

- [ ] 12.1 Update `src/processors/podcast_script_generator.py`:
  - Replace `from src.services.tavily_service import get_tavily_service`
  - Use `from src.services.web_search import get_web_search_provider`
  - `_handle_web_search()` calls `provider.search()` + `provider.format_results()`
- [ ] 12.2 Update `src/api/chat_routes.py`:
  - Change `web_search_enabled=bool(settings.tavily_api_key)` to check any configured provider:
    `web_search_enabled=bool(settings.tavily_api_key or settings.perplexity_api_key or settings.xai_api_key)`
  - Ensure chat web search delegates to `get_web_search_provider()` instead of direct Tavily calls

## 13. Scheduled Web Search Sources (sources.d)

> `[depends: 10.1]` — needs orchestrator functions for perplexity and xsearch.
> **File scope**: `sources.d/websearch.yaml`, `src/config/source_loader.py`, `src/cli/pipeline_commands.py`

- [ ] 13.1 Create `sources.d/websearch.yaml` with example entries:
  ```yaml
  defaults:
    type: websearch
    enabled: true

  sources:
    - name: "AI Weekly Roundup"
      provider: perplexity
      prompt: "Latest AI model releases, research breakthroughs, and industry news"
      tags: [ai, weekly]

    - name: "AI Twitter Pulse"
      provider: grok
      prompt: "Find AI research announcements, model releases, and technical discussions on X"
      tags: [ai, social]
      max_threads: 30
  ```
- [ ] 13.2 Add `WebSearchSource` dataclass and `load_websearch_sources()` to source loader:
  ```python
  @dataclass
  class WebSearchSource:
      name: str
      provider: str  # "perplexity" | "grok"
      prompt: str
      enabled: bool = True
      tags: list[str] = field(default_factory=list)
      # Provider-specific overrides
      max_results: int | None = None       # perplexity
      max_threads: int | None = None       # grok
      recency_filter: str | None = None    # perplexity
      context_size: str | None = None      # perplexity
  ```
- [ ] 13.3 Update pipeline `_run_ingestion_stage_async()` to read websearch sources:
  - Load enabled entries from `sources.d/websearch.yaml`
  - For each entry, dispatch to `ingest_perplexity_search()` or `ingest_xsearch()` with entry's prompt and options
  - Run all websearch sources as parallel tasks alongside existing ingestion sources
  - Guard each provider: skip if API key not configured

## 14. Pipeline Integration (Perplexity standalone)

> `[depends: 10.1]` — needs orchestrator function.
> **File scope**: `src/cli/pipeline_commands.py`

- [ ] 14.1 Add `ingest_perplexity_search` to `_run_ingestion_stage_async()` in `src/cli/pipeline_commands.py`
- [ ] 14.2 Register as parallel source alongside existing sources
- [ ] 14.3 Guard with `settings.perplexity_api_key` — skip silently if not configured

## 15. Tests — WebSearchProvider Protocol and Adapters

> `[depends: 1.1, 2.1, 8.1, 9.1]` — needs all provider implementations.
> **File scope**: `tests/test_services/test_web_search.py`

- [ ] 15.1 Create `tests/test_services/test_web_search.py`:
  - Test `get_web_search_provider()` factory with each setting value (`tavily`, `perplexity`, `grok`)
  - Test factory raises/warns for unknown provider values
  - Test factory with explicit `provider` parameter override
- [ ] 15.2 Test `TavilyWebSearchProvider`:
  - Mock `TavilyClient`, verify `search()` returns `WebSearchResult` objects
  - Test `format_results()` output format
  - Test graceful handling when API key not configured
- [ ] 15.3 Test `PerplexityWebSearchProvider`:
  - Mock `openai.OpenAI` client
  - Verify `extra_body` contains Perplexity-specific params
  - Test citation mapping to `WebSearchResult.citations`
  - Test `format_results()` includes numbered citation links
- [ ] 15.4 Test `GrokWebSearchProvider`:
  - Mock `GrokXClient.search()` response
  - Verify synthesized text is parsed into `WebSearchResult` objects
  - Test handling when Grok returns no extractable URLs (empty `url` field)
  - Test `max_results` limiting

## 16. Tests — Perplexity Ingestion

> `[depends: 5.2, 6.1]` — needs client and service implementations.
> **File scope**: `tests/test_ingestion/test_perplexity_search.py`

- [ ] 16.1 Create `tests/test_ingestion/test_perplexity_search.py`:
  - Test `PerplexityResponse` model creation and validation
  - Test ContentData conversion (markdown formatting, metadata)
  - Test source_id generation from citation hashes
  - Test deduplication: exact match, citation overlap, content hash
- [ ] 16.2 Test `PerplexityClient`:
  - Mock `openai.OpenAI` client
  - Verify `extra_body` contains Perplexity-specific params
  - Test error handling (auth error, rate limit, network error)
  - Test response parsing with citations array
- [ ] 16.3 Test `PerplexityContentIngestionService`:
  - Mock client, mock DB
  - Test full ingestion flow: search → parse → dedup → persist
  - Test SAVEPOINT isolation for partial failures
  - Test prompt retrieval from PromptService
  - Test `close()` called even on error

## 17. Tests — Orchestrator and CLI

> `[depends: 10.1, 11.1]` — needs orchestrator and CLI implementations.
> **File scope**: `tests/test_ingestion/test_perplexity_search.py`, `tests/cli/test_ingest_commands.py`

- [ ] 17.1 Add orchestrator tests:
  - Mock at `src.ingestion.perplexity_search.PerplexityContentIngestionService`
  - Verify `on_result` callback receives full result
  - Verify `service.close()` called in all paths
- [ ] 17.2 Add CLI tests to `tests/cli/test_ingest_commands.py`:
  - Test success path with default options
  - Test with custom prompt and options
  - Test with --force flag
  - Test failure path
  - Test JSON mode output
  - Test help text
- [ ] 17.3 Test pipeline integration:
  - Verify perplexity-search included in pipeline sources
  - Verify graceful skip when API key not configured

## 18. Tests — Scheduled Web Search Sources

> `[depends: 13.2]` — needs source loader implementation.
> **File scope**: `tests/test_config/test_source_loader.py` (or new file)

- [ ] 18.1 Test `load_websearch_sources()`:
  - Test loading valid `websearch.yaml` with mixed providers
  - Test disabled entries are filtered out
  - Test defaults applied correctly
  - Test provider-specific fields (max_threads, recency_filter) parsed
  - Test empty/missing file returns empty list
- [ ] 18.2 Test pipeline dispatch:
  - Mock orchestrator functions
  - Verify correct provider called per source entry
  - Verify provider-specific options passed through
  - Verify sources with unconfigured API keys are skipped

## 19. Tests — Consumer Wiring

> `[depends: 12.1]` — needs consumer updates.
> **File scope**: `tests/test_processors/`, `tests/api/`

- [ ] 19.1 Test podcast script generator uses `get_web_search_provider()`:
  - Mock provider factory
  - Verify `_handle_web_search()` delegates to configured provider
- [ ] 19.2 Test chat routes `web_search_enabled` reflects any configured provider:
  - Test with only Tavily configured → enabled
  - Test with only Perplexity configured → enabled
  - Test with only Grok configured → enabled
  - Test with none configured → disabled

## 20. Documentation

> `[depends: 11.1, 13.1]` — needs CLI and source config implementations.

- [ ] 20.1 Update CLAUDE.md:
  - Add `aca ingest perplexity-search` to CLI commands section
  - Add `PERPLEXITY_API_KEY`, `PERPLEXITY_MODEL`, `WEB_SEARCH_PROVIDER` to configuration
  - Add `sources.d/websearch.yaml` to source configuration section
  - Add gotcha: "Perplexity citations may contain inline `[N]` markers — always use `citations` response field, not inline URLs"
  - Add gotcha: "`WEB_SEARCH_PROVIDER` controls ad-hoc search only — ingestion uses provider from `sources.d/websearch.yaml` entries"
- [ ] 20.2 Update `docs/SETUP.md` with Perplexity API key setup instructions
