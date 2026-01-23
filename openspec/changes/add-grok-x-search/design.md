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

### Decision 5: Thread as Unit of Content

**What**: Each Content record represents a complete thread (or single post if not a thread). The thread is the atomic unit that gets summarized.

**Content Structure**:

```python
# markdown_content example for a thread
"""
# @author_handle - Thread Title or First Line

**Posted**: 2025-01-23 14:30 UTC
**Thread**: 5 posts
**Engagement**: 1.2K likes, 450 retweets, 89 replies (root post)

## Thread Content

### 1/5
The first post in the thread...

### 2/5
Continuing the discussion...

### 3/5
More details here...

### 4/5
Technical specifics...

### 5/5
Conclusion and links.

## Media

- [Image 1](https://x.com/...)
- [Video](https://x.com/...)

## Links

- [Linked Article](https://example.com/...)

## Source

[View thread on X](https://x.com/author/status/123456789)
"""

# metadata_json structure
{
    "root_post_id": "123456789",           # First/root post ID (used as source_id)
    "thread_post_ids": [                    # ALL post IDs in thread (for deduplication)
        "123456789",
        "123456790",
        "123456791",
        "123456792",
        "123456793"
    ],
    "author_handle": "author_handle",
    "author_name": "Author Display Name",
    "author_followers": 50000,
    "posted_at": "2025-01-23T14:30:00Z",
    "likes": 1200,                          # Root post engagement
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
- Thread is the natural unit of discourse on X - splitting threads loses context
- markdown_content provides complete narrative for summarization
- Summarizer receives full thread context to generate meaningful summary
- metadata_json enables filtering, sorting, and analysis
- Engagement metrics help prioritize high-signal content

### Decision 6: Thread-Aware Deduplication Strategy

**What**: Use root_post_id as source_id for stable thread identification, and check incoming post IDs against all stored thread_post_ids arrays to prevent duplicate thread records.

**Deduplication algorithm**:
1. For each discovered post, determine if it's part of a thread
2. If thread: fetch the complete thread and use root_post_id as source_id
3. Before inserting, check if source_id (root_post_id) already exists
4. Also query metadata_json to check if ANY of the thread's post_ids exist in any stored thread_post_ids array
5. If match found: skip (or update if force_reprocess)
6. Content hash serves as final fallback for edge cases

**Why**:
- Root post ID provides stable, canonical identifier for threads
- Storing all thread_post_ids enables deduplication when different posts from the same thread are encountered on separate runs
- Example: Run 1 finds post #3 of thread T → stores thread with root_id and all post_ids
- Run 2 finds post #1 of same thread T → detects post #1 exists in stored thread_post_ids → skips
- Content hash catches remaining edge cases (deleted/recreated posts)

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
