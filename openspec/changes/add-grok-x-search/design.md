# Design: Grok API X News Search Integration

## Context

The xAI Grok API provides server-side agentic tool calling with `x_search` for searching X (Twitter) posts. Unlike traditional APIs that return raw search results, Grok's agentic approach uses an LLM to iteratively search, analyze, and synthesize information. This makes it particularly effective for discovering relevant AI news across the noisy X platform.

**Stakeholders**: Content ingestion pipeline, summarization pipeline, digest creation

## Goals / Non-Goals

### Goals
- Ingest AI-relevant X posts as Content records
- Support configurable search prompts for different AI topics
- Integrate seamlessly with existing summarization and digest pipelines
- Provide structured output suitable for both human review and LLM processing
- Deduplicate posts across ingestion runs

### Non-Goals
- Real-time streaming of X posts (batch ingestion only)
- User authentication for private X accounts
- Posting or interacting with X (read-only)
- Replacing other content sources (complementary)

## Decisions

### Decision 1: Use xAI Python SDK with Streaming

**What**: Use the official `xai-sdk` package (v1.3.1+) with streaming mode for tool calling.

**Why**:
- Official SDK provides stable, well-tested interface
- Streaming mode is recommended by xAI for agentic tool calling
- Provides real-time observability of search process
- Handles authentication, retries, and error handling

**Alternatives considered**:
- Raw HTTP API calls: More control but requires implementing auth, streaming, error handling manually
- Third-party SDKs: Less reliable, may not support latest features

### Decision 2: Model Selection - grok-4-1-fast

**What**: Use `grok-4-1-fast` model for X search queries.

**Why**:
- Specifically trained by xAI to excel at agentic tool calling
- Optimized for speed while maintaining quality
- Recommended by xAI documentation for search use cases

**Alternatives considered**:
- `grok-3`: Older model, not optimized for tool calling
- `grok-4-1`: Full model, higher cost without significant benefit for search

### Decision 3: ContentSource Enum Value

**What**: Add `XPOST = "xpost"` to `ContentSource` enum.

**Why**:
- Clear, concise identifier matching our naming convention (lowercase)
- Distinguishes from potential future Twitter/X integrations (e.g., direct API)
- Aligns with other sources: `gmail`, `rss`, `youtube`

**Alternatives considered**:
- `X = "x"`: Too short, unclear
- `TWITTER = "twitter"`: Outdated branding
- `X_SEARCH = "x_search"`: Describes method not source

### Decision 4: Agentic Prompt-Based Discovery

**What**: Use configurable LLM prompts to guide Grok's search behavior rather than simple keyword queries.

**Why**:
- Grok's agentic nature means it can interpret complex requests
- Prompts like "Find recent AI research announcements, model releases, and technical discussions" yield better results than keyword searches
- Allows customization per ingestion run or scheduled job
- Can specify date ranges, author filters, and relevance criteria in natural language

**Example prompts**:
```
"Search X for AI news from the past 24 hours. Focus on:
- New model releases from OpenAI, Anthropic, Google, Meta, xAI
- Research paper announcements with links
- Technical discussions about LLMs, RAG, agents
- AI startup funding announcements
Return detailed information including author handles and engagement metrics."
```

### Decision 5: Content Structure for X Posts

**What**: Store X posts with the following structure:

```python
# markdown_content example
"""
# @author_handle - Post Title or First Line

**Posted**: 2025-01-23 14:30 UTC
**Engagement**: 1.2K likes, 450 retweets, 89 replies

## Content

The full post text goes here, including any threads...

## Media

- [Image 1](https://x.com/...)
- [Video](https://x.com/...)

## Links

- [Linked Article](https://example.com/...)

## Source

[View on X](https://x.com/author/status/123456789)
"""

# metadata_json structure
{
    "post_id": "123456789",
    "author_handle": "author_handle",
    "author_name": "Author Display Name",
    "author_followers": 50000,
    "posted_at": "2025-01-23T14:30:00Z",
    "likes": 1200,
    "retweets": 450,
    "replies": 89,
    "is_thread": true,
    "thread_length": 5,
    "media_urls": ["https://..."],
    "linked_urls": ["https://..."],
    "hashtags": ["AI", "LLM"],
    "mentions": ["@openai", "@anthropic"],
    "search_query": "original prompt used"
}
```

**Why**:
- markdown_content provides human-readable format and works with existing summarization
- metadata_json enables filtering, sorting, and analysis
- Engagement metrics help prioritize high-signal posts
- Thread support captures full context

### Decision 6: Deduplication Strategy

**What**: Deduplicate using post_id as source_id, with content_hash as backup.

**Why**:
- X post IDs are globally unique and stable
- Content hash catches edge cases (same content from different search runs)
- Matches existing Content deduplication pattern

### Decision 7: Rate Limiting and Cost Control

**What**: Implement configurable `max_posts_per_search` and `max_tool_turns` limits.

**Why**:
- xAI charges $5 per 1000 successful tool calls
- `max_turns` limits how many search iterations Grok performs
- Prevents runaway costs from overly broad queries
- Default: `max_turns=5`, `max_posts_per_search=50`

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| API cost overruns | Configurable limits, cost tracking in metadata_json |
| Rate limiting by xAI | Implement exponential backoff, respect rate limit headers |
| Search quality varies | Iterative prompt refinement, manual review option |
| X posts lack depth | Combine with other sources in digests, not replace |
| Grok API changes | Pin SDK version, monitor changelog |

## Migration Plan

1. Add `xai-sdk>=1.3.1` to dependencies
2. Create Alembic migration to add `xpost` to content_source enum
3. Implement client and service classes
4. Add configuration settings and environment variables
5. No data migration needed (additive feature)

## Open Questions

1. **Search frequency**: How often should we run X searches? (Proposed: configurable, default daily)
2. **Prompt templates**: Should we maintain a library of search prompts? (Proposed: start with single configurable prompt, expand as needed)
3. **Author filtering**: Should we maintain a list of AI-relevant accounts to prioritize? (Proposed: let Grok discover organically initially, add filtering later if needed)
