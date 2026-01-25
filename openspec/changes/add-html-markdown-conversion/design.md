# Design: HTML to Markdown Conversion

## Context

The content aggregator ingests content from multiple sources (Gmail, RSS feeds, YouTube). HTML content from web sources loses formatting during conversion, degrading LLM processing quality. This design introduces a two-tier extraction system optimized for both speed and quality.

**Stakeholders**: Content ingestion pipeline, LLM summarization, end users viewing digests

**Constraints**:
- Must be self-hosted (no external API dependencies)
- Processing ~100 content items/week with potential for growth
- Current stack: Python/TypeScript/PostgreSQL
- Docker available for deployment
- Pipeline is moving to async processing patterns

## Goals / Non-Goals

**Goals**:
- Preserve document structure (headings, lists, tables, code blocks)
- Fast processing for most content (<100ms)
- Graceful fallback for JavaScript-heavy content
- Quality validation before storage
- Native async implementation for pipeline integration
- Support both RSS feed URLs and Gmail HTML bodies

**Non-Goals**:
- Real-time streaming extraction
- Image/media content extraction (handled separately)
- Translation or language detection (future enhancement)
- Custom site-specific scrapers

## Decisions

### Decision 1: Trafilatura as Primary Extractor

**What**: Use Trafilatura for first-pass HTML extraction

**Why**:
- Pure Python, no external services or browser instances
- Benchmarked as academic-best for content extraction
- Built-in RSS/ATOM feed discovery
- Fast execution (~50ms per page)
- Minimal dependencies

**Alternatives considered**:
- **BeautifulSoup + html2text**: Lower quality extraction, more manual work
- **Newspaper3k**: Abandoned project, security concerns
- **Crawl4AI only**: Too slow for primary path (2-5s per page)

### Decision 2: Crawl4AI as Fallback

**What**: Use Crawl4AI when Trafilatura output fails quality checks

**Why**:
- JavaScript rendering via headless browser handles dynamic content
- "Fit Markdown" removes boilerplate automatically
- Docker-ready for consistent deployment
- Content filtering strategies (Pruning, BM25)

**Alternatives considered**:
- **Playwright/Puppeteer direct**: More setup, no markdown optimization
- **Firecrawl**: Similar features but less established
- **Jina ReaderLM**: Requires GPU, overkill for this use case

### Decision 3: Quality-Based Fallback Triggering

**What**: Automatically fall back to Crawl4AI based on output quality metrics

**Criteria**:
- Content length < 200 characters
- Missing expected structure (no headings/paragraphs)
- Unmatched code blocks

**Why**: Avoids slow path for content that extracts well with Trafilatura while ensuring quality for difficult content.

### Decision 4: Native Async Architecture

**What**: Implement converter as fully async to align with pipeline modernization

```python
async def convert(self, url: str, force_crawl4ai: bool = False) -> str | None:
    """Convert URL with automatic fallback - async native."""
    if force_crawl4ai:
        return await self._convert_with_crawl4ai(url)

    # Trafilatura is sync, run in thread pool
    result = await asyncio.to_thread(self._convert_with_trafilatura, url)

    if self._passes_quality_check(result):
        return result

    if self.use_fallback:
        return await self._convert_with_crawl4ai(url)

    return result
```

**Why**:
- Pipeline is moving to async patterns for performance
- Crawl4AI is async-native, no wrapper overhead
- Trafilatura (sync) runs efficiently via `asyncio.to_thread()`
- Enables efficient batch processing with `asyncio.gather()`
- Aligns with existing `*ContentIngestionService` async patterns

### Decision 5: Dual Input Mode (URL and Raw HTML)

**What**: Support both URL fetching and direct HTML string conversion

**Why**:
- RSS feeds: Need URL fetching for article content
- Gmail: Already have HTML body, no need to fetch

```python
async def convert(
    self,
    url: str | None = None,
    html: str | None = None,
    force_crawl4ai: bool = False
) -> str | None:
    """Convert URL or raw HTML to markdown."""
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HtmlMarkdownConverter                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input (URL or HTML)                                        │
│       │                                                     │
│       ▼                                                     │
│  Trafilatura (async via to_thread)                          │
│       │                                                     │
│       ▼                                                     │
│  Quality Check ────────────────► Return Markdown            │
│       │ (fails)                                             │
│       ▼                                                     │
│  Crawl4AI (async native) ──────► Return Markdown            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Integration Points:
  ├─ RSSContentIngestionService: convert(url=article_url)
  └─ GmailContentIngestionService: convert(html=email_body)

Quality Check:
  ├─ Length > 200 chars?
  ├─ Has headings (#)?
  ├─ Has paragraphs (\n\n)?
  └─ Code blocks balanced (``` count even)?
```

## Component Design

### HtmlMarkdownConverter

```python
class HtmlMarkdownConverter:
    """Two-tier HTML to Markdown converter with async support."""

    def __init__(self, use_crawl4ai_fallback: bool = True):
        self.use_fallback = use_crawl4ai_fallback

    async def convert(
        self,
        url: str | None = None,
        html: str | None = None,
        force_crawl4ai: bool = False
    ) -> str | None:
        """Convert URL or raw HTML to markdown with automatic fallback."""
        ...

    async def _convert_with_trafilatura(
        self,
        url: str | None = None,
        html: str | None = None
    ) -> str | None:
        """Primary extraction via thread pool."""
        ...

    async def _convert_with_crawl4ai(self, url: str) -> str | None:
        """Fallback extraction - async native."""
        ...

    def _passes_quality_check(self, markdown: str | None) -> bool:
        """Quick quality gate check."""
        ...
```

### Quality Validator

```python
def validate_markdown_quality(markdown: str, min_length: int = 200) -> dict:
    """Check extraction quality."""
    return {
        "valid": bool,
        "issues": list[str],
        "stats": {
            "length": int,
            "has_headings": bool,
            "has_links": bool,
            "code_blocks": int
        }
    }
```

### Batch Processing (Async)

```python
async def batch_convert(
    self,
    items: list[dict],  # [{"url": ...} or {"html": ...}]
    max_concurrent: int = 10
) -> list[dict]:
    """Process multiple items concurrently."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_one(item: dict) -> dict:
        async with semaphore:
            try:
                result = await self.convert(**item)
                return {"input": item, "markdown": result, "success": True}
            except Exception as e:
                return {"input": item, "error": str(e), "success": False}

    return await asyncio.gather(*[process_one(item) for item in items])
```

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Crawl4AI adds heavy dependency (browser) | Larger Docker image, resource usage | Make Crawl4AI optional with feature flag |
| Trafilatura may miss dynamic content | Some content poorly extracted | Quality-based fallback catches most cases |
| Rate limiting by source sites | Extraction failures | Implement retry with exponential backoff |
| Memory usage for batch processing | OOM on large batches | Use semaphore to limit concurrency |
| Crawl4AI not applicable for raw HTML | Gmail fallback limited | Trafilatura handles most email HTML well |

## Migration Plan

### Phase 1: Core Implementation
1. Add dependencies to requirements.txt
2. Create `src/parsers/html_markdown.py` module
3. Add quality validation utilities
4. Unit tests with sample HTML fixtures

### Phase 2: Pipeline Integration
1. Update `RSSContentIngestionService` to use converter with URL mode
2. Update `GmailContentIngestionService` to use converter with HTML mode
3. Add configuration for fallback behavior
4. Integration tests with real sources

### Phase 3: Docker & Production
1. Add Crawl4AI to docker-compose (optional service)
2. Environment variable configuration
3. Monitoring for extraction quality metrics

### Rollback
- Feature flag to disable new converter
- Fall back to existing extraction method
- No schema changes required

## Open Questions

1. **Should we cache Crawl4AI browser instance?** - Could improve fallback performance but adds complexity
2. **Should we expose extraction method choice in API?** - Might be useful for debugging
3. **What's the right quality threshold?** - 200 chars is initial guess, may need tuning based on real data
4. **Gmail HTML fallback strategy?** - Crawl4AI needs URLs; for Gmail we rely on Trafilatura quality
