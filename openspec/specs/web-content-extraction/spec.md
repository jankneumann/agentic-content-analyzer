# web-content-extraction Specification

## Purpose
TBD - created by archiving change add-html-markdown-conversion. Update Purpose after archive.
## Requirements
### Requirement: Two-Tier HTML to Markdown Conversion

The system SHALL convert HTML content from web sources to well-formatted markdown using a two-tier extraction approach: Trafilatura for primary extraction and Crawl4AI for fallback.

#### Scenario: Extract RSS article from URL
- **GIVEN** a URL pointing to an RSS feed article
- **WHEN** the URL is processed through the converter with `url` parameter
- **THEN** Trafilatura fetches and extracts the content
- **AND** the result is well-formatted markdown with preserved headings, lists, and links
- **AND** processing completes in under 100ms

#### Scenario: Extract Gmail HTML body
- **GIVEN** raw HTML content from a Gmail email body
- **WHEN** the HTML is processed through the converter with `html` parameter
- **THEN** Trafilatura extracts the content without URL fetching
- **AND** the result is well-formatted markdown
- **AND** plain text structure is preserved

#### Scenario: Fallback for JavaScript-heavy content
- **GIVEN** a URL pointing to a page with dynamically loaded content
- **WHEN** Trafilatura returns content shorter than 200 characters
- **THEN** the converter falls back to Crawl4AI
- **AND** Crawl4AI renders JavaScript and extracts content
- **AND** the result is well-formatted markdown

#### Scenario: Both extractors fail
- **GIVEN** a URL that cannot be accessed or parsed
- **WHEN** both Trafilatura and Crawl4AI fail to extract content
- **THEN** the converter returns None
- **AND** an error is logged with the failure reason

---

### Requirement: Async-Native Conversion

The system SHALL implement HTML-to-markdown conversion as async-native to integrate with the pipeline's async processing patterns.

#### Scenario: Async URL conversion
- **GIVEN** an async context in the ingestion pipeline
- **WHEN** `await converter.convert(url=article_url)` is called
- **THEN** Trafilatura runs via `asyncio.to_thread()` for non-blocking execution
- **AND** Crawl4AI fallback runs as native async
- **AND** the calling coroutine is not blocked

#### Scenario: Async batch conversion
- **GIVEN** a list of 10 content items to convert
- **WHEN** `await converter.batch_convert(items, max_concurrent=5)` is called
- **THEN** items are processed concurrently with semaphore limiting
- **AND** results are collected via `asyncio.gather()`
- **AND** individual failures do not stop the batch

---

### Requirement: Markdown Quality Validation

The system SHALL validate extracted markdown quality before accepting it, checking structure and completeness.

#### Scenario: Validate complete extraction
- **GIVEN** markdown content with headings, paragraphs, and links
- **AND** content length exceeds 200 characters
- **WHEN** quality validation runs
- **THEN** validation passes
- **AND** stats include content metrics (length, heading count, link count)

#### Scenario: Detect incomplete extraction
- **GIVEN** markdown content shorter than 200 characters
- **WHEN** quality validation runs
- **THEN** validation fails with "Content too short" issue
- **AND** the converter triggers fallback if enabled

#### Scenario: Detect malformed code blocks
- **GIVEN** markdown content with unbalanced code block markers
- **WHEN** quality validation runs
- **THEN** validation reports "Unmatched code blocks" issue
- **AND** the issue is included in validation stats

---

### Requirement: Trafilatura Primary Extraction

The system SHALL use Trafilatura as the primary extraction method for speed and quality, supporting both URL fetching and raw HTML input.

#### Scenario: Configure Trafilatura for URL extraction
- **GIVEN** a URL to extract
- **WHEN** Trafilatura is invoked with `fetch_url()` and `extract()`
- **THEN** output format is set to markdown
- **AND** formatting preservation is enabled (bold, italic, etc.)
- **AND** links and tables are included
- **AND** metadata extraction is enabled

#### Scenario: Configure Trafilatura for raw HTML
- **GIVEN** raw HTML content from Gmail
- **WHEN** Trafilatura `extract()` is called directly with HTML string
- **THEN** content is extracted without network request
- **AND** the same markdown options are applied

#### Scenario: Extract RSS feed URLs
- **GIVEN** a website URL
- **WHEN** RSS feed discovery is requested
- **THEN** Trafilatura's feed finder locates available feeds
- **AND** all discovered feed URLs are returned

#### Scenario: Handle extraction timeout
- **GIVEN** a URL that takes too long to fetch
- **WHEN** Trafilatura exceeds timeout threshold
- **THEN** extraction fails gracefully
- **AND** fallback is triggered if enabled

---

### Requirement: Crawl4AI Fallback Extraction

The system SHALL use Crawl4AI as a fallback extractor for URL-based content requiring JavaScript rendering.

#### Scenario: Render JavaScript content
- **GIVEN** a URL requiring JavaScript for content display
- **WHEN** Crawl4AI processes the URL
- **THEN** a headless browser renders the page
- **AND** content filtering removes boilerplate
- **AND** fit_markdown output is returned

#### Scenario: Configure content filtering
- **GIVEN** Crawl4AI extraction is triggered
- **WHEN** the browser renders the page
- **THEN** PruningContentFilter removes noise (threshold=0.45)
- **AND** minimum word threshold filters short blocks

#### Scenario: Handle browser unavailable
- **GIVEN** Crawl4AI fallback is enabled
- **WHEN** the headless browser fails to launch
- **THEN** extraction fails gracefully
- **AND** error is logged with browser failure details
- **AND** None is returned

#### Scenario: Fallback not applicable for raw HTML
- **GIVEN** raw HTML input (not a URL)
- **WHEN** Trafilatura extraction fails quality check
- **THEN** Crawl4AI fallback is skipped (requires URL)
- **AND** the Trafilatura result is returned as-is
- **AND** a warning is logged

---

### Requirement: RSS Content Ingestion Integration

The system SHALL integrate HTML-to-markdown conversion into the RSS content ingestion pipeline.

#### Scenario: Convert RSS article during ingestion
- **GIVEN** an RSS feed item with article URL
- **WHEN** RSSContentIngestionService processes the item
- **THEN** HtmlMarkdownConverter is called with `url=article_url`
- **AND** converted markdown is stored in Content.markdown_content
- **AND** extraction metrics are logged

#### Scenario: Handle RSS conversion failure
- **GIVEN** an RSS article URL that fails conversion
- **WHEN** the converter returns None
- **THEN** Content record is created with empty markdown_content
- **AND** Content.status is set to indicate parsing failure
- **AND** error details are logged

---

### Requirement: Gmail Content Ingestion Integration

The system SHALL integrate HTML-to-markdown conversion into the Gmail content ingestion pipeline.

#### Scenario: Convert HTML email during ingestion
- **GIVEN** a Gmail message with HTML body
- **WHEN** GmailContentIngestionService processes the message
- **THEN** HtmlMarkdownConverter is called with `html=email_body`
- **AND** converted markdown is stored in Content.markdown_content
- **AND** extraction metrics are logged

#### Scenario: Preserve plain text emails
- **GIVEN** a Gmail message with plain text body only
- **WHEN** GmailContentIngestionService processes the message
- **THEN** HtmlMarkdownConverter is not invoked
- **AND** plain text is stored directly in Content.markdown_content

#### Scenario: Handle Gmail conversion failure
- **GIVEN** an HTML email body that fails conversion
- **WHEN** the converter returns None
- **THEN** original HTML is stored as fallback
- **AND** Content.status indicates partial processing
- **AND** warning is logged

---

### Requirement: Extraction Configuration

The system SHALL support configuration of extraction behavior through settings.

#### Scenario: Disable Crawl4AI fallback
- **GIVEN** configuration with `use_crawl4ai_fallback=False`
- **WHEN** Trafilatura returns short content
- **THEN** no fallback is attempted
- **AND** the short content is returned as-is

#### Scenario: Force Crawl4AI extraction
- **GIVEN** a URL and `force_crawl4ai=True` parameter
- **WHEN** conversion is requested
- **THEN** Trafilatura is skipped
- **AND** Crawl4AI is used directly

#### Scenario: Adjust quality threshold
- **GIVEN** configuration with `min_length_threshold=500`
- **WHEN** extracted content is 300 characters
- **THEN** fallback is triggered due to length check

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
