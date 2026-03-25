# Design: Blog Page Scraping Ingestion

## Architecture Decision

### Approach: New Source Type Following RSS Pattern

The blog scraper follows the established **client-service pattern** used by RSS, podcast, and other ingestion sources:

```
BlogScrapingClient (fetch + parse)
    ↓
BlogContentIngestionService (dedup + persist)
    ↓
orchestrator.ingest_blog() (lazy import + wire up)
    ↓
CLI: aca ingest blog / Pipeline: _run_ingestion()
```

### Why a New Source Type (Not URL Ingestion)

The existing `aca ingest url` handles single URLs manually. Blog scraping is fundamentally different:
- **Discovery**: Automatically finds post links from an index page
- **Batch**: Processes multiple posts per source in one run
- **Scheduled**: Runs as part of the daily pipeline
- **Configured**: Defined in `sources.d/` YAML, not ad-hoc

### Why Not Extend RSS

RSS ingestion uses `feedparser` for structured feed parsing. Blog index pages are unstructured HTML with no standard format. The link discovery logic is different enough to warrant a separate module, though it reuses the same content extraction infrastructure (Trafilatura, `HtmlMarkdownConverter`).

## Detailed Design

### 1. Source Configuration (`sources.d/blogs.yaml`)

```yaml
defaults:
  type: blog
  enabled: true

sources:
  - name: "Anthropic Blog"
    url: "https://www.anthropic.com/research"
    tags: [ai, anthropic]
    max_entries: 10

  - name: "Claude Blog"
    url: "https://claude.ai/blog"
    tags: [ai, claude]
    link_selector: "a[href*='/blog/']"  # Optional CSS selector for post links
    max_entries: 5
```

**Source fields:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `url` | str | yes | - | Blog index/listing page URL |
| `name` | str | no | domain | Publication name for Content records |
| `link_selector` | str | no | auto | CSS selector to find post links on index page |
| `link_pattern` | str | no | none | Regex pattern to filter discovered URLs |
| `max_entries` | int | no | 10 | Maximum posts to ingest per run |
| `tags` | list | no | [] | Tags applied to ingested content |
| `request_delay` | float | no | 1.0 | Seconds between requests (rate limiting) |

### 2. Source Model (`src/config/sources.py`)

```python
class BlogSource(SourceBase):
    type: Literal["blog"] = "blog"
    url: str
    link_selector: str | None = None
    link_pattern: str | None = None
    request_delay: float = 1.0
```

Added to the `Source` discriminated union and `SourcesConfig.get_blog_sources()`.

### 3. Blog Scraping Client (`src/ingestion/blog_scraper.py`)

Two-phase approach:

**Phase 1: Link Discovery**
1. Fetch the blog index page via `httpx.Client` (with SSRF protection, same as `URLExtractor`)
2. Parse HTML with BeautifulSoup
3. Extract links using either:
   - **Configured CSS selector** (`link_selector`): `soup.select(selector)` for `href` attributes
   - **Heuristic detection**: Find `<a>` tags within `<article>`, `<main>`, or common blog post list patterns
4. Resolve relative URLs to absolute
5. Filter by `link_pattern` regex if configured
6. Deduplicate URLs
7. Return ordered list of `(url, title_hint)` tuples (title from link text)

**Phase 2: Content Extraction**
For each discovered URL (up to `max_entries`):
1. Check deduplication (skip if `source_url` exists in DB)
2. Fetch and extract via `HtmlMarkdownConverter.convert(url=post_url)` (reuses Trafilatura)
3. Extract metadata: title, author, published_date from `<meta>` tags and structured data
4. Build `ContentData` with `source_type=BLOG`, `source_id=f"blog:{post_url}"`
5. Respect `request_delay` between fetches

**Date Extraction Strategy:**
1. `<meta property="article:published_time">` (Open Graph)
2. `<time datetime="...">` elements
3. `<meta name="date">` or `<meta name="DC.date">`
4. JSON-LD `datePublished` in `<script type="application/ld+json">`
5. Fallback: ingestion timestamp

**Heuristic Link Discovery (when no `link_selector`):**
```python
# Priority order of selectors tried:
BLOG_POST_SELECTORS = [
    "article a[href]",              # Links inside <article> elements
    "main a[href]",                 # Links inside <main>
    ".post a[href]",                # Common blog post class
    ".blog-post a[href]",
    "[class*='post'] a[href]",
    "[class*='article'] a[href]",
    "[class*='entry'] a[href]",
]
```

Filter discovered links:
- Must be same domain (or subdomain) as the index page
- Must not match common non-article patterns: `/tag/`, `/category/`, `/author/`, `/page/`, `/about`, `/contact`, `#`
- Must have a path longer than the index page path (deeper URL = likely a post)

### 4. Content Ingestion Service

```python
class BlogContentIngestionService:
    def ingest_content(
        self,
        sources: list[BlogSource] | None = None,
        max_entries_per_source: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> IngestionResult:
```

Follows `RSSContentIngestionService` pattern exactly:
1. Resolve sources from parameter or `sources.d/blogs.yaml`
2. For each source: discover links, extract content, deduplicate, persist
3. Return `IngestionResult` with per-source results

**Deduplication (3 levels, same as RSS):**
1. `source_type + source_id` unique constraint (`blog:{url}`)
2. `source_url` check (catches URL variants)
3. `content_hash` (catches same content from different sources)

### 5. ContentSource Enum

Add `BLOG = "blog"` to `ContentSource` in `src/models/content.py`.

This requires an Alembic migration to add the value to the PostgreSQL enum:
```sql
ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'blog';
```

### 6. Orchestrator Integration

```python
# src/ingestion/orchestrator.py
def ingest_blog(
    *,
    max_entries_per_source: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    on_result: Callable | None = None,
) -> int:
    from src.ingestion.blog_scraper import BlogContentIngestionService
    service = BlogContentIngestionService()
    result = service.ingest_content(...)
    return result.items_ingested
```

### 7. Pipeline Runner Integration

In `_run_ingestion()`:
```python
sources: list[tuple[str, Callable[[], int]]] = [
    ("gmail", ingest_gmail),
    ("rss", ingest_rss),
    ("blog", ingest_blog),  # New
    ...
]
```

### 8. CLI Integration

```bash
aca ingest blog [--max N] [--days N] [--force]
```

Follows the same pattern as `aca ingest rss`.

## Alternatives Considered

### A. Use LLM to Extract Links
An LLM could analyze the HTML and identify blog post links more intelligently. Rejected because:
- Unnecessary cost for a structural task
- CSS selectors + heuristics are reliable for blog index pages
- LLM adds latency per source

### B. Reuse WEBPAGE Source Type
Could use `ContentSource.WEBPAGE` instead of adding `BLOG`. Rejected because:
- `WEBPAGE` is for single ad-hoc URLs; `BLOG` is for scheduled batch discovery
- Distinct source type enables filtering in digests (`--source blog`)
- Clearer semantics in the pipeline

### C. RSS Auto-Discovery
Try to find RSS feeds automatically before falling back to scraping. Could be a nice-to-have but out of scope — if the user knows about an RSS feed, they'd configure it as an RSS source.

## File Changes Summary

| File | Change |
|------|--------|
| `src/config/sources.py` | Add `BlogSource` model, update `Source` union, add `get_blog_sources()` |
| `src/models/content.py` | Add `BLOG = "blog"` to `ContentSource` enum |
| `src/ingestion/blog_scraper.py` | **New**: `BlogScrapingClient` + `BlogContentIngestionService` |
| `src/ingestion/orchestrator.py` | Add `ingest_blog()` function |
| `src/pipeline/runner.py` | Add `("blog", ingest_blog)` to source list |
| `src/cli/ingest_commands.py` | Add `blog` subcommand |
| `sources.d/blogs.yaml` | **New**: Blog source configuration |
| `alembic/versions/xxx_add_blog_source.py` | **New**: Migration to add `blog` to PG enum |
| `tests/test_ingestion/test_blog_scraper.py` | **New**: Unit tests |
