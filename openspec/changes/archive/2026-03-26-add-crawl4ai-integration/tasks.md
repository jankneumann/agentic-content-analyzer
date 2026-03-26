# Tasks: Add Crawl4AI Integration

## Phase 1: Configuration & Dependencies (wp-config)

- [x] 1.1 Add `crawl4ai>=0.7.0` to `pyproject.toml` as optional dependency group
  ```toml
  [project.optional-dependencies]
  crawl4ai = ["crawl4ai>=0.7.0"]
  ```
- [x] 1.2 Add Settings fields to `src/config/settings.py`:
  - `crawl4ai_enabled: bool = False`
  - `crawl4ai_cache_mode: str = "bypass"` (bypass/enabled/disabled/read_only/write_only)
  - `crawl4ai_server_url: str | None = None`
  - `crawl4ai_page_timeout: int = 30000`
  - `crawl4ai_excluded_tags: list[str] = ["nav", "footer", "header"]`
- [x] 1.3 Add `${CRAWL4AI_*}` interpolation references in `profiles/base.yaml`
  ```yaml
  settings:
    crawl4ai:
      crawl4ai_enabled: ${CRAWL4AI_ENABLED:-false}
      crawl4ai_cache_mode: ${CRAWL4AI_CACHE_MODE:-bypass}
      crawl4ai_server_url: ${CRAWL4AI_SERVER_URL:-}
      crawl4ai_page_timeout: ${CRAWL4AI_PAGE_TIMEOUT:-30000}
  ```
- [x] 1.4 Write unit tests for new Settings fields (`tests/config/test_settings_crawl4ai.py`)
  - Test defaults
  - Test env var override
  - Test profile interpolation with `_env_file=None`

## Phase 2: Converter Updates (wp-converter)

- [x] 2.1 Update `HtmlMarkdownConverter.__init__()` to read from `get_settings()`
  - Accept `None` sentinels for constructor kwargs
  - Fall back to settings values when not explicitly passed
  - Preserve existing constructor override capability for tests
- [x] 2.2 Add CacheMode mapping in `src/parsers/html_markdown.py`
  ```python
  CACHE_MODE_MAP = {
      "bypass": CacheMode.BYPASS,
      "enabled": CacheMode.ENABLED,
      "disabled": CacheMode.DISABLED,
      "read_only": CacheMode.READ_ONLY,
      "write_only": CacheMode.WRITE_ONLY,
  }
  ```
  - Map string setting to enum at init time
  - Raise `ValueError` for invalid cache mode strings
  - Handle gracefully when crawl4ai not installed (lazy import)
- [x] 2.3 Add `crawl4ai_excluded_tags` to `CrawlerRunConfig` in `_convert_with_crawl4ai()`
- [x] 2.4 Add configurable `page_timeout` to `CrawlerRunConfig`
- [x] 2.5 Add remote server mode: `_convert_with_crawl4ai_remote()`
  - Use `httpx.AsyncClient` to `POST /md` at `crawl4ai_server_url`
  - JSON body: `{"url": url, "c": cache_mode_string}`
  - Timeout: `page_timeout / 1000 + 5` seconds
  - Parse response: `data.get("result", {}).get("markdown", None)`
  - Handle connection errors, timeouts, non-200 responses gracefully
- [x] 2.6 Update `_convert_with_crawl4ai()` to dispatch local vs remote
  - If `self.server_url` is set → call `_convert_with_crawl4ai_remote()`
  - Else → use existing `AsyncWebCrawler` in-process path
- [x] 2.7 Write unit tests for converter updates (`tests/parsers/test_html_markdown_crawl4ai.py`)
  - Test settings injection via `__init__`
  - Test CacheMode mapping (valid + invalid)
  - Test remote mode HTTP call (mock httpx)
  - Test remote mode error handling (connection refused, timeout, 500)
  - Test local vs remote dispatch logic
  - Test excluded_tags and page_timeout propagation

## Phase 3: Docker & Infrastructure (wp-docker)

- [x] 3.1 Add `crawl4ai` service to `docker-compose.yml`
  ```yaml
  crawl4ai:
    image: unclecode/crawl4ai:latest
    container_name: newsletter-crawl4ai
    ports:
      - "11235:11235"
    shm_size: '1g'
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:11235/health || exit 1"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 30s
    profiles:
      - crawl4ai
  ```
- [x] 3.2 Add Makefile targets
  - `crawl4ai-up`: start with `--profile crawl4ai`, wait for health
  - `crawl4ai-down`: stop service
  - `crawl4ai-logs`: tail logs
  - `test-crawl4ai`: run `pytest -m crawl4ai`
- [x] 3.3 Register `crawl4ai` pytest marker in `pyproject.toml`
  ```toml
  [tool.pytest.ini_options]
  markers = [
      "crawl4ai: Tests requiring Crawl4AI browser or Docker server",
  ]
  ```
- [x] 3.4 Add Crawl4AI server status to `/ready` health check response
  - Check if `crawl4ai_server_url` is configured
  - If so, include `crawl4ai: {status, url}` in readiness response
  - Use `httpx.AsyncClient` for non-blocking health probe

## Phase 4: Integration Tests (wp-tests)

- [x] 4.1 Create Hoverfly simulation for Crawl4AI REST API
  - `tests/integration/fixtures/simulations/crawl4ai_md_success.json`
  - `tests/integration/fixtures/simulations/crawl4ai_md_error.json`
  - Simulate `POST /md` with markdown response body
- [x] 4.2 Create integration test fixture (`tests/integration/fixtures/crawl4ai.py`)
  - `crawl4ai_available` session-scoped fixture
  - `requires_crawl4ai` skip marker
  - `crawl4ai_url` fixture from settings
- [x] 4.3 Write integration tests (`tests/integration/test_crawl4ai_extraction.py`)
  - Test via Hoverfly (no real browser needed)
  - Test full fallback chain: Trafilatura short → Crawl4AI remote → success
  - Test remote mode with various HTTP response codes
  - Mark with `@pytest.mark.crawl4ai`
- [x] 4.4 Write live integration tests (require Docker)
  - Test against real Crawl4AI Docker service
  - JS-heavy page extraction (e.g., SPA content)
  - Mark with `@pytest.mark.crawl4ai` for conditional execution

## Phase 5: Documentation (wp-docs)

- [x] 5.1 Update `docs/SETUP.md` — add Crawl4AI section
  - Local install: `uv pip install -e ".[crawl4ai]" && crawl4ai-setup`
  - Docker install: `make crawl4ai-up`
  - Configuration: settings table with env vars
  - Verification: `crawl4ai-doctor` and `make verify-profile`
- [x] 5.2 Update `docs/ARCHITECTURE.md` — extraction pipeline diagram
  - Show two-tier flow: Trafilatura → quality check → Crawl4AI (local/remote)
- [x] 5.3 Update `CLAUDE.md` — add gotchas
  - `Crawl4AI Docker needs --shm-size=1g` for browser stability
  - `crawl4ai_enabled defaults to False` — must explicitly enable
  - `Remote mode needs Docker running` — `make crawl4ai-up` first
  - `CacheMode string must match enum names` — bypass/enabled/disabled/read_only/write_only
- [x] 5.4 Update `docs/TESTING.md` — add Crawl4AI test section
  - Hoverfly simulation pattern
  - `@pytest.mark.crawl4ai` marker usage
  - Docker requirements for live tests

## Task Dependencies

```
Phase 1 (wp-config)
  ├── Phase 2 (wp-converter) — needs settings fields
  ├── Phase 3 (wp-docker) — needs pytest marker + settings
  └── Phase 5 (wp-docs) — needs settings + docker defined
Phase 2 + Phase 3
  └── Phase 4 (wp-tests) — needs converter + docker + fixtures
```

Phases 2, 3, and 5 can run **in parallel** after Phase 1 completes.
Phase 4 depends on both Phase 2 and Phase 3.
