# Design: Unified Web Search Provider with Perplexity Integration

## Goals
- Unify Tavily, Perplexity, and Grok behind a single `WebSearchProvider` abstraction for both ad-hoc search and scheduled ingestion
- Ingest AI-relevant web articles as Content records via Perplexity Sonar
- Enable configurable scheduled web searches via `sources.d/websearch.yaml`
- Follow the established Protocol-based provider pattern (like `RerankProvider`, `BM25SearchStrategy`)
- Reuse the OpenAI SDK (no new SDK dependency)

### Non-Goals
- Replacing Tavily as the default ad-hoc web search provider (Perplexity and Grok are opt-in)
- Real-time streaming search (batch ingestion only)
- Using the Perplexity standalone Search API (raw snippets) — we want synthesized answers with citations
- Content scraping or full-page extraction (we ingest synthesized summaries with citation links)
- Auto-splitting broad prompts into sub-queries (users define explicit prompts in `sources.d/websearch.yaml`)
- Making Tavily an ingestion source (Tavily's API is optimized for brief tool-use queries, not content discovery)

## Decisions

### Decision 1: Use OpenAI SDK with Custom Base URL (Perplexity)

**What**: Use the existing `openai` Python SDK with `base_url="https://api.perplexity.ai"` instead of adding the official Perplexity Python SDK.

**Why**:
- Zero new dependencies — `openai` is already in our dependency tree
- Matches how xSearch uses the xAI SDK (also OpenAI-compatible)
- Perplexity-specific params passed via `extra_body` dict
- Simpler maintenance and fewer supply-chain risks

**Alternatives considered**:
- Official `perplexityai` Python SDK: adds a dependency, provides native type hints but limited adoption
- Raw `httpx` calls: too low-level, no streaming support out of the box

### Decision 2: Model Selection — `sonar` (with `sonar-pro` option)

**What**: Default to `sonar` model for ingestion searches. Configurable via `PERPLEXITY_MODEL` setting.

**Why**:
- `sonar` (127k ctx): Fast, cost-effective ($1/M input, $1/M output + $5-8/1K requests)
- `sonar-pro` (200k ctx): ~2x more citations, better for complex multi-step queries ($3/M input, $15/M output)
- Daily AI news search is well within `sonar`'s capabilities
- Users can upgrade to `sonar-pro` via settings for deeper research runs

### Decision 3: ContentSource Enum Value

**What**: Add `PERPLEXITY = "perplexity"` to `ContentSource` enum.

**Why**:
- Describes the discovery method (Perplexity web search), consistent with `xsearch` pattern
- Clear, lowercase identifier matching existing convention
- Distinguishes from potential future direct URL scraping

### Decision 4: Citation-Based Content Structure

**What**: Each Content record represents one search query's synthesized response. Citations become the primary value — each cited URL is stored in metadata for downstream linking and deduplication.

**Content Structure**:

```python
# markdown_content example
"""
# AI Model Releases This Week

## Summary

Several major AI labs released new models this week. Anthropic announced
Claude 4.5 Haiku [1], while Google released Gemini 2.5 Pro [2]. Meta
published LLaMA 4 Maverick [3] with significantly improved multilingual
capabilities.

## Key Developments

### Claude 4.5 Haiku
Anthropic's latest model focuses on speed and cost-efficiency...

### Gemini 2.5 Pro
Google's flagship model now supports native image generation...

## Sources

1. [Anthropic Blog: Claude 4.5 Haiku](https://anthropic.com/blog/...)
2. [Google AI Blog: Gemini 2.5 Pro](https://blog.google/...)
3. [Meta AI: LLaMA 4 Maverick](https://ai.meta.com/...)
"""

# metadata_json structure
{
    "search_query": "AI model releases this week",
    "search_prompt": "Find the latest AI model releases...",
    "model_used": "sonar",
    "search_context_size": "medium",
    "citations": [
        "https://anthropic.com/blog/...",
        "https://blog.google/...",
        "https://ai.meta.com/..."
    ],
    "citation_count": 3,
    "search_recency_filter": "week",
    "domain_filter": [],
    "tokens_used": {
        "prompt": 150,
        "completion": 800,
        "total": 950
    },
    "related_questions": [
        "What are the benchmark results for Claude 4.5 Haiku?",
        "How does LLaMA 4 compare to previous versions?"
    ]
}
```

**Why**:
- Synthesized content provides complete narrative for summarization
- Citations enable linking back to original sources
- Related questions can seed follow-up searches
- Token usage enables cost tracking
- Content hash based on citations array provides stable dedup key

### Decision 5: Deduplication Strategy

**What**: Multi-level dedup using citation URL overlap, content hash, and source_id.

**Deduplication algorithm**:
1. Generate `source_id` as `perplexity:{hash(sorted(citations))}` — stable ID based on cited sources
2. Check if `source_id` already exists in Content table
3. Check for significant citation overlap: if >50% of new citations appear in any existing perplexity Content's `metadata_json->'citations'`, skip
4. Content hash serves as final fallback

**Why**:
- Different search prompts may discover the same underlying articles
- Citation-based dedup catches this: "AI model releases" and "latest from Anthropic" may cite the same blog post
- Threshold (50%) allows partial overlap without false positives

### Decision 6: WebSearchProvider Protocol (Unified Abstraction)

**What**: Create a `WebSearchProvider` protocol in `src/services/web_search.py` that Tavily, Perplexity, and Grok all implement. This serves two use cases:
1. **Ad-hoc search**: Used by chat, podcast script generation, and digest review as an LLM tool
2. **Ingestion source**: Used by the pipeline to run scheduled searches and persist results as Content records

```python
@runtime_checkable
class WebSearchProvider(Protocol):
    @property
    def name(self) -> str:
        """Provider identifier: 'tavily', 'perplexity', 'grok'."""
        ...

    def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]:
        """Execute a web search and return structured results."""
        ...

    def format_results(self, results: list[WebSearchResult]) -> str:
        """Format results as a string for LLM consumption."""
        ...

@dataclass
class WebSearchResult:
    title: str
    url: str
    content: str
    score: float | None = None
    citations: list[str] | None = None   # Perplexity-specific: source URLs
    metadata: dict[str, Any] | None = None  # Provider-specific extras

def get_web_search_provider(provider: str | None = None) -> WebSearchProvider:
    """Factory function. Uses settings.web_search_provider if provider not specified."""
```

**Why**:
- Follows the established Protocol pattern from `RerankProvider` and `BM25SearchStrategy`
- `name` property enables logging/metrics per provider
- `citations` field in `WebSearchResult` accommodates Perplexity's richer results without breaking Tavily/Grok
- Factory accepts optional provider override for cases where a specific provider is needed (e.g., sources.d entries)
- Future providers (Brave, Google Search, Bing) drop in without changing consumers

**Provider implementations**:
- `TavilyWebSearchProvider`: Wraps existing `TavilyService.search()` → maps to `WebSearchResult`
- `PerplexityWebSearchProvider`: Uses `PerplexityClient` for API calls, maps citations to results
- `GrokWebSearchProvider`: Adapts `GrokXClient` (see Decision 8)

### Decision 7: Configurable Search Parameters

**What**: Expose Perplexity-specific parameters through Settings for fine-tuning.

```python
# Settings fields
perplexity_api_key: str | None = None       # PERPLEXITY_API_KEY
perplexity_model: str = "sonar"              # PERPLEXITY_MODEL
perplexity_search_context_size: str = "medium"  # low|medium|high
perplexity_search_recency_filter: str = "week"  # hour|day|week|month|year
perplexity_max_results: int = 30             # Max articles per search run
perplexity_domain_filter: list[str] = []     # Domain allow/deny list
web_search_provider: str = "tavily"          # tavily|perplexity|grok (for ad-hoc search)
```

**Why**:
- `search_context_size` directly controls cost ($5 vs $12 per 1K requests)
- `search_recency_filter` ensures we get recent content, not historical
- `domain_filter` allows targeting AI-specific sites (arxiv.org, openai.com, etc.)
- `web_search_provider` now supports all three providers
- All configurable via env vars, profiles, or CLI flags

### Decision 8: Grok Ad-Hoc Search Adapter

**What**: Create a `GrokWebSearchProvider` that adapts the existing `GrokXClient` for ad-hoc search use in the `WebSearchProvider` protocol.

**Challenge**: Grok's `x_search` is a server-side tool — the xAI SDK calls Grok, which autonomously searches X and returns a synthesized response. This is fundamentally different from Tavily/Perplexity's simple query→results pattern:
- Tavily/Perplexity: `query → list[{title, url, content}]`
- Grok: `prompt → synthesized_text` (may contain multiple threads/posts)

**Adapter design**:
```python
class GrokWebSearchProvider:
    """Adapts GrokXClient for the WebSearchProvider protocol."""

    def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]:
        # 1. Call GrokXClient.search(prompt=query) to get synthesized text
        # 2. Parse the response to extract individual thread/post references
        # 3. Map each thread to a WebSearchResult:
        #    - title: "{author_handle}: {first_line_of_post}"
        #    - url: "https://x.com/{handle}/status/{post_id}" (if extractable)
        #    - content: synthesized summary of the thread
        #    - metadata: {"author", "engagement", "is_thread"}
        # 4. Limit to max_results
        return results
```

**Why**:
- Reuses existing `GrokXClient` without modifying its core search logic
- The adapter transforms Grok's synthesized output into structured `WebSearchResult` objects
- For ingestion, the full `GrokXContentIngestionService` is still used (richer metadata, thread-aware dedup)
- For ad-hoc search (chat/podcast), the lighter adapter is sufficient — we just need titles/URLs/summaries
- If Grok has no extractable URLs (server-side tool doesn't always return them), the `url` field is empty and `content` carries the full synthesized answer

**Alternatives considered**:
- Making `GrokXContentIngestionService` implement `WebSearchProvider` directly: too much coupling, the ingestion service manages DB persistence and dedup which is irrelevant for ad-hoc search
- Skipping Grok from the ad-hoc abstraction: leaves the architecture incomplete and means chat can't use X search results

### Decision 9: Scheduled Web Search Sources (`sources.d/websearch.yaml`)

**What**: Add a new source configuration file for defining scheduled web searches that run during the pipeline.

```yaml
# sources.d/websearch.yaml
defaults:
  type: websearch
  enabled: true

sources:
  # Perplexity: broad AI/tech web search
  - name: "AI Weekly Roundup"
    provider: perplexity
    prompt: "Latest AI model releases, research breakthroughs, and industry news this week"
    tags: [ai, weekly]

  - name: "AI Infrastructure & Tools"
    provider: perplexity
    prompt: "New developer tools, frameworks, and infrastructure for AI/ML engineering"
    tags: [ai, tools]

  # Grok: X/Twitter social signal
  - name: "AI Twitter Pulse"
    provider: grok
    prompt: "Find AI research announcements, model releases, and technical discussions on X"
    tags: [ai, social]
    max_threads: 30

  - name: "Data Engineering Twitter"
    provider: grok
    prompt: "Find data engineering discussions, new tools, and best practices on X"
    tags: [data, social]
    max_threads: 20
```

**Why**:
- Replaces the user's current 2-prompt external workflow with in-app configuration
- Each entry is a named, tagged source — same pattern as RSS, YouTube, podcasts
- `provider` field explicitly selects which web search backend to use
- Provider-specific options (e.g., `max_threads` for Grok, `recency_filter` for Perplexity) are passed through
- Pipeline reads all enabled websearch entries and dispatches to the appropriate provider
- Easy to add/remove searches without code changes

**Source loading**:
- `SourceLoader` gets a new `load_websearch_sources()` method
- Returns `list[WebSearchSource]` dataclass with `name`, `provider`, `prompt`, `tags`, `enabled`, plus provider-specific overrides
- Pipeline iterates entries and calls `ingest_perplexity_search()` or `ingest_xsearch()` per provider

**Alternatives considered**:
- Separate files per provider (`xsearch.yaml`, `perplexity.yaml`): loses the unified view of all web search sources
- Database-stored searches: over-engineering — YAML is sufficient and consistent with all other source types
- Tavily as ingestion provider: Tavily's API is optimized for brief context-enrichment queries (3-5 results), not content discovery. Only Perplexity and Grok are suitable for scheduled ingestion.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Perplexity API cost overruns | Default to `sonar` with medium context. Configurable limits. Cost tracking in metadata. |
| Citation URL overlap with existing RSS/newsletter content | Dedup by citation URL. Track `source_url` in metadata for cross-source dedup in future. |
| Search quality varies by prompt | Iterative prompt refinement via PromptService. Users can override per-run via CLI or per-source via sources.d. |
| Perplexity may hallucinate URLs | Only use URLs from `citations` response field, never from inline content. Validate URL format. |
| Rate limiting | Default rate limits (Perplexity: 50 RPM, Grok: configurable) are ample. Add exponential backoff. |
| OpenAI SDK compatibility breaks | Pin OpenAI SDK version. Perplexity-specific params are in `extra_body` (stable). |
| Grok ad-hoc search returns synthesized text without clean URLs | Adapter returns empty `url` and full `content` — consumers already handle results without clickable links (Tavily snippets work the same way). |
| Three providers increases configuration complexity | Tavily remains the default with zero configuration. Perplexity and Grok are opt-in. `sources.d/websearch.yaml` uses a familiar pattern. |

## Migration Plan

1. Add Perplexity settings and `web_search_provider` to `src/config/settings.py` and `profiles/base.yaml`
2. Create `WebSearchProvider` protocol and factory in `src/services/web_search.py`
3. Adapt `TavilyService` to implement `WebSearchProvider` protocol
4. Create Alembic migration to add `perplexity` to `content_source` enum
5. Implement Perplexity client and ingestion service
6. Create `PerplexityWebSearchProvider` for ad-hoc search
7. Create `GrokWebSearchProvider` adapter for ad-hoc search
8. Wire consumers (podcast generator, chat routes) to use `get_web_search_provider()`
9. Add `sources.d/websearch.yaml` support to source loader
10. Wire pipeline to read websearch sources and dispatch to appropriate providers
11. No data migration needed (additive feature)

## Open Questions

1. **Cross-source deduplication**: Should we skip ingesting a Perplexity result if its cited URLs already appear as existing Content from RSS/Gmail? (Proposed: defer to future, start with per-provider dedup only)
2. **Source scheduling granularity**: Should `sources.d/websearch.yaml` entries support per-source recency filters and domain filters? (Proposed: yes, as optional per-entry overrides that default to global settings)
3. **Tavily as ingestion source**: Should Tavily be available as a `sources.d/websearch.yaml` provider? (Proposed: no — Tavily's API returns brief snippets optimized for tool use, not full content suitable for ingestion)
