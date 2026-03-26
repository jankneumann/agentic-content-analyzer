# Web Content Extraction Spec Delta

## ADDED Requirements

### Requirement: Crawl4AI Fallback for JavaScript Content

The system SHALL use Crawl4AI as a fallback extractor for JavaScript-heavy pages when Trafilatura produces insufficient content.

#### Scenario: Fallback triggered for JS-heavy page
- **GIVEN** a URL pointing to a JavaScript-rendered page
- **AND** Crawl4AI is enabled via configuration (`crawl4ai_enabled=True`)
- **WHEN** Trafilatura extraction returns content below the quality threshold
- **THEN** the system SHALL automatically retry with Crawl4AI
- **AND** the extraction method SHALL be logged as "crawl4ai"

#### Scenario: Crawl4AI disabled by default
- **GIVEN** a fresh installation without Crawl4AI setup
- **WHEN** extraction is attempted on any URL
- **THEN** only Trafilatura SHALL be used
- **AND** no browser launch SHALL be attempted
- **AND** no HTTP requests to Crawl4AI server SHALL be made

---

### Requirement: Crawl4AI Configuration via Settings

The system SHALL support configuration of Crawl4AI behavior via the unified Settings class and profile system.

#### Scenario: Enable Crawl4AI via settings
- **GIVEN** `crawl4ai_enabled=True` in configuration
- **AND** Crawl4AI is available (local install or remote server)
- **WHEN** extraction quality validation fails
- **THEN** Crawl4AI fallback SHALL be attempted

#### Scenario: Cache mode configuration
- **GIVEN** `crawl4ai_cache_mode` is set to a valid mode string
- **WHEN** Crawl4AI extraction is invoked
- **THEN** the mode string SHALL be mapped to the corresponding `CacheMode` enum value
- **AND** the cache behavior SHALL match the selected mode:
  - `bypass` — skip reads, still write (default)
  - `enabled` — read from and write to cache
  - `disabled` — no caching at all
  - `read_only` — read from cache, never write
  - `write_only` — write to cache, never read

#### Scenario: Invalid cache mode string
- **GIVEN** `crawl4ai_cache_mode` is set to an unrecognized string
- **WHEN** `HtmlMarkdownConverter` is initialized
- **THEN** the system SHALL raise `ValueError` with available options listed

#### Scenario: Page timeout configuration
- **GIVEN** `crawl4ai_page_timeout` is set to a custom value (ms)
- **WHEN** Crawl4AI processes a URL
- **THEN** the page load timeout SHALL be set to the configured value

#### Scenario: Excluded tags configuration
- **GIVEN** `crawl4ai_excluded_tags` is set to a list of HTML tag names
- **WHEN** Crawl4AI processes a URL
- **THEN** the specified tags SHALL be excluded from content extraction

#### Scenario: Constructor override for testing
- **GIVEN** `HtmlMarkdownConverter` is instantiated with explicit constructor kwargs
- **WHEN** settings also define Crawl4AI configuration
- **THEN** constructor kwargs SHALL take precedence over settings
- **AND** this enables isolated unit testing without settings patching

---

### Requirement: Remote Server Deployment Mode

The system SHALL support delegating Crawl4AI extraction to a remote Docker-hosted server via REST API.

#### Scenario: Remote extraction via HTTP
- **GIVEN** `crawl4ai_server_url` is configured (e.g., `http://localhost:11235`)
- **WHEN** Crawl4AI extraction is triggered
- **THEN** the system SHALL send `POST /md` to the remote server
- **AND** the request body SHALL include `{"url": "<target-url>", "c": "<cache_mode>"}`
- **AND** local browser launch SHALL NOT occur

#### Scenario: Remote server unavailable
- **GIVEN** `crawl4ai_server_url` is configured
- **AND** the remote server is not reachable
- **WHEN** Crawl4AI extraction is triggered
- **THEN** the system SHALL log a warning with connection details
- **AND** the system SHALL return the Trafilatura result (even if short)
- **AND** content ingestion SHALL NOT fail

#### Scenario: Remote server returns error
- **GIVEN** a remote Crawl4AI server returns HTTP 500
- **WHEN** extraction is attempted
- **THEN** the system SHALL log the error status code
- **AND** fall back to the Trafilatura result
- **AND** content ingestion SHALL NOT fail

#### Scenario: Local mode when no server URL
- **GIVEN** `crawl4ai_enabled=True` AND `crawl4ai_server_url` is not set
- **AND** Crawl4AI is installed locally (`import crawl4ai` succeeds)
- **WHEN** Crawl4AI extraction is triggered
- **THEN** the system SHALL use `AsyncWebCrawler` in-process
- **AND** no HTTP requests to external servers SHALL be made

---

### Requirement: Docker Service Configuration

The system SHALL provide a Docker Compose service definition for running Crawl4AI as a containerized server.

#### Scenario: Start Crawl4AI Docker service
- **GIVEN** `docker-compose.yml` includes a `crawl4ai` service
- **WHEN** `make crawl4ai-up` or `docker compose --profile crawl4ai up -d` is executed
- **THEN** the Crawl4AI container SHALL start with port 11235 exposed
- **AND** the container SHALL have `shm_size=1g` for browser stability
- **AND** the container SHALL pass health checks within 60 seconds

#### Scenario: Health check for readiness
- **GIVEN** Crawl4AI is deployed as a Docker service
- **AND** `crawl4ai_server_url` is configured in settings
- **WHEN** the application `/ready` endpoint is queried
- **THEN** the response SHALL include Crawl4AI service status
- **AND** the status SHALL reflect the Docker health check result

---

### Requirement: Fail-Safe Integration

The system SHALL maintain the existing fail-safe design where extraction failures never block content ingestion.

#### Scenario: Crawl4AI import unavailable in local mode
- **GIVEN** `crawl4ai_enabled=True` AND `crawl4ai_server_url` is not set
- **AND** the `crawl4ai` package is NOT installed
- **WHEN** extraction quality validation fails
- **THEN** the system SHALL log a warning that Crawl4AI is enabled but not installed
- **AND** the Trafilatura result SHALL be returned as-is
- **AND** no exception SHALL propagate to the ingestion service

#### Scenario: Graceful degradation chain
- **GIVEN** any combination of Trafilatura and Crawl4AI failures
- **WHEN** `converter.convert()` completes
- **THEN** the result SHALL be one of:
  - Trafilatura markdown (quality passes)
  - Crawl4AI markdown (fallback succeeds)
  - Short Trafilatura markdown (both fail, returned anyway)
  - `None` (only when both extractors return nothing)
- **AND** no unhandled exceptions SHALL escape the converter
