# Design: Document Search with Hybrid BM25 + Vector Search

## Prerequisites

This design assumes the **refactor-unified-content-model** change is complete:
- Single `contents` table replaces Newsletter + Document
- All content stored as markdown in `Content.markdown_content`
- Summaries and digests use markdown with section conventions

## Context

The newsletter aggregator ingests content from multiple sources (Gmail, RSS, file uploads, YouTube, Substack) and stores it in PostgreSQL. Users need to search across this content efficiently using natural language queries. The current ILIKE search on titles is insufficient for finding content by concepts, searching full document text, or ranking results by relevance.

The system supports three PostgreSQL backends with different extension availability:

| Extension | Local PostgreSQL | Supabase | Neon |
|-----------|------------------|----------|------|
| **pgvector** | Install manually | Built-in | Built-in |
| **pg_search (ParadeDB)** | Install manually | Available | **Not available** |
| **PostgreSQL Native FTS** | Built-in | Built-in | Built-in |

This design integrates cross-backend compatibility from day one via abstraction protocols, rather than hardcoding a single backend and abstracting later.

**Stakeholders**: End users searching for content, API consumers, digest generation (finding related historical content), programmatic agents (Deep Research Agent)

**Constraints**:
- Must work with existing PostgreSQL infrastructure (Docker Compose setup)
- Must work identically (API semantics) across all three backends
- Should not require external search services (Elasticsearch, Typesense)
- Embedding generation adds latency and cost at ingestion time
- Must handle incremental updates (new documents added continuously)
- Cannot require pg_search on Neon (not available)

## Goals / Non-Goals

**Goals**:
- Full-text search across all document content with relevance scoring
- Semantic search using embeddings for conceptual matching
- Hybrid search combining both approaches with configurable weighting
- Sub-second search latency for typical queries
- Automatic index updates on document insertion/update
- Filtering by source, date range, publication, status
- Cross-backend compatibility with graceful degradation
- Pluggable embedding providers for cost/quality/privacy tradeoffs
- Search response metadata for debugging and agent reasoning

**Non-Goals**:
- Real-time search (within milliseconds of ingestion) — slight delay acceptable
- Federated search across Neo4j knowledge graph (separate capability)
- Query suggestions/autocomplete (future enhancement)
- Multi-language search (English-only initially)
- Identical search quality across backends (native FTS < BM25, documented)

## Decisions

### Decision 1: BM25 Strategy Abstraction

**What**: Define a `BM25SearchStrategy` protocol with two implementations — ParadeDB BM25 (higher quality) and PostgreSQL Native FTS (universal fallback) — selected at runtime based on database backend.

**Why**:
- pg_search is unavailable on Neon, so we cannot hardcode it
- Follows existing provider pattern established by `DatabaseProvider`
- Enables testing with mock strategies
- Allows future strategies (e.g., pg_trgm for fuzzy matching)

**Implementation**:

```python
# src/services/search.py
from typing import Protocol

class BM25SearchStrategy(Protocol):
    """Protocol for BM25/keyword search implementations."""

    @property
    def name(self) -> str: ...

    async def search(
        self,
        query: str,
        limit: int = 100,
        source_types: list[str] | None = None,
    ) -> list[tuple[int, int]]:
        """Returns list of (chunk_id, rank) tuples, 1-indexed."""
        ...

    def get_required_columns(self) -> list[str]: ...


class ParadeDBBM25Strategy:
    """Uses pg_search extension for true BM25 ranking."""
    name = "paradedb_bm25"

    async def search(self, query: str, limit: int = 100, ...) -> list[tuple[int, int]]:
        stmt = text("""
            SELECT id, paradedb.score(id) as score
            FROM document_chunks
            WHERE chunk_text @@@ :query
            ORDER BY score DESC LIMIT :limit
        """)
        ...

class PostgresNativeFTSStrategy:
    """Uses PostgreSQL native full-text search with ts_rank_cd."""
    name = "postgres_native_fts"

    async def search(self, query: str, limit: int = 100, ...) -> list[tuple[int, int]]:
        stmt = text("""
            SELECT id, ts_rank_cd(search_vector, plainto_tsquery('english', :query)) as rank
            FROM document_chunks
            WHERE search_vector @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC LIMIT :limit
        """)
        ...
```

**Alternatives considered**:
- Single implementation with feature flags: Less testable, harder to extend
- Separate search services per backend: Code duplication
- PostgreSQL native FTS only: Lower quality than BM25 on backends that support pg_search

### Decision 2: Backend Auto-Detection Factory

**What**: Factory function that auto-detects pg_search availability and selects the best BM25 strategy, with optional explicit override.

**Why**:
- Reuses existing provider detection infrastructure
- Zero-config for most deployments
- Allows explicit override for testing or forced degradation

**Implementation**:

```python
# src/services/search_factory.py
def get_bm25_strategy(session: Session) -> BM25SearchStrategy:
    """
    Selection order:
    1. Explicit override via SEARCH_BM25_STRATEGY env var
    2. pg_search if available (Supabase, local with extension)
    3. PostgreSQL native FTS (fallback, works everywhere)
    """
    override = settings.search_bm25_strategy
    if override == "paradedb":
        return ParadeDBBM25Strategy(session)
    elif override == "native":
        return PostgresNativeFTSStrategy(session)

    if _check_pg_search_available(session):
        return ParadeDBBM25Strategy(session)
    return PostgresNativeFTSStrategy(session)

def _check_pg_search_available(session: Session) -> bool:
    result = session.execute(text(
        "SELECT 1 FROM pg_extension WHERE extname = 'pg_search'"
    ))
    return result.fetchone() is not None
```

### Decision 3: Pluggable Embedding Providers

**What**: Define an `EmbeddingProvider` protocol with implementations for OpenAI, Voyage AI, Cohere, and local sentence-transformers, selected via configuration.

**Why**:
- Different providers optimize for different use cases (cost, quality, privacy)
- Voyage AI specifically optimizes for RAG/retrieval scenarios
- Local models enable air-gapped deployments
- Provider switching should not require code changes
- Already have OpenAI integration for Graphiti

**Supported providers**:

| Provider | Default Model | Dimensions | Max Tokens | Cost |
|----------|--------------|------------|------------|------|
| OpenAI | text-embedding-3-small | 1536 | 8191 | $0.02/1M |
| Voyage AI | voyage-3 | 1024 | 32000 | $0.06/1M |
| Cohere | embed-english-v3.0 | 1024 | 512 | $0.10/1M |
| Local | all-MiniLM-L6-v2 | 384 | 256 | Free |

**Implementation**:

```python
# src/services/embedding.py
class EmbeddingProvider(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def dimensions(self) -> int: ...
    @property
    def max_tokens(self) -> int: ...
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

def get_embedding_provider() -> EmbeddingProvider:
    provider_name = settings.embedding_provider.lower()
    model = settings.embedding_model
    if provider_name == "openai":
        return OpenAIEmbeddingProvider(model or "text-embedding-3-small")
    elif provider_name == "voyage":
        return VoyageEmbeddingProvider(model or "voyage-3")
    elif provider_name == "cohere":
        return CohereEmbeddingProvider(model or "embed-english-v3.0")
    elif provider_name == "local":
        return LocalEmbeddingProvider(model or "all-MiniLM-L6-v2")
    else:
        raise ValueError(f"Unknown embedding provider: {provider_name}")
```

**Cohere note**: Uses `input_type="search_document"` for indexing and `input_type="search_query"` for query embedding — this asymmetry is handled internally by the provider.

**Trade-off**: Changing embedding provider with different dimensions requires re-creating the vector column and re-indexing all content.

### Decision 4: Semantic Chunking with Parser Integration

**What**: Chunk documents into semantically meaningful units that leverage existing parser infrastructure. Strategy is determined by `Content.parser_used` since all content is markdown under the unified model.

**Why**:
- Embedding entire documents loses semantic precision for long content
- Parsers already extract rich structural information we should leverage
- Chunk-level search enables precise snippet highlighting and navigation
- YouTube timestamps enable deep-linking to exact video moments

**Chunking strategies by parser**:

| Parser | Approach | Boundaries | Metadata |
|--------|----------|------------|----------|
| DoclingParser | Section + paragraph | H1-H6, page breaks, table boundaries | Page number, section title |
| YouTubeParser | Timestamp segments | 30-second windows with sentence boundaries | Video timestamp, deep-link URL |
| MarkItDownParser | Markdown structure | Headings, list boundaries, code blocks | Section path |
| Default (Gmail/RSS) | Heading-based | H1/H2/H3, paragraphs | Publication, author |
| Summaries/Digests | Section headers | `## Section` boundaries | Section type, theme tags |

**Chunk size targets** (global defaults, overridable per-source):
- Target: ~512 tokens per chunk
- Overlap: ~64 tokens between consecutive chunks (context continuity)
- Tables: Kept whole even if exceeding target (up to 2048 tokens)
- YouTube segments: Grouped to ~30 seconds (natural speech units)

These defaults can be overridden at the source level — see Decision 10.

**Table handling**: Tables from DoclingParser are their own chunks (`chunk_type="table"`) with caption and headers prepended as context.

### Decision 5: DocumentChunk Data Model

**What**: Store chunks in a `document_chunks` table with structural metadata, embedding, and native FTS support.

**Implementation**:

```python
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int]                          # PK
    content_id: Mapped[int]                  # FK to contents table
    chunk_text: Mapped[str]                  # Text content
    chunk_index: Mapped[int]                 # Order within document (0, 1, 2...)

    # Structural metadata
    section_path: Mapped[str | None]         # "# Heading > ## Subheading"
    heading_text: Mapped[str | None]         # Nearest heading above chunk
    chunk_type: Mapped[str]                  # "paragraph", "table", "code", "quote", "transcript", "section"

    # Location anchors
    page_number: Mapped[int | None]          # For PDFs
    start_char: Mapped[int | None]           # Character offset in source
    end_char: Mapped[int | None]
    timestamp_start: Mapped[float | None]    # For YouTube (seconds)
    timestamp_end: Mapped[float | None]
    deep_link_url: Mapped[str | None]        # Direct link to chunk location

    # Search columns
    embedding: Mapped[Vector | None]         # pgvector, dimensions from settings
    search_vector: Mapped[TSVECTOR | None]   # Native FTS, auto-updated via trigger

    created_at: Mapped[datetime]
```

**Indexes**:
- `content_id` — FK lookups and cascade deletes
- HNSW on `embedding` — fast approximate nearest neighbor
- GIN on `search_vector` — fast native FTS queries
- BM25 on `chunk_text` — ParadeDB index (created only if pg_search available)
- Composite `(chunk_type)` — filtering by chunk type

**TSVECTOR trigger** auto-updates `search_vector` on INSERT/UPDATE of `chunk_text`:

```sql
CREATE OR REPLACE FUNCTION document_chunks_search_vector_update()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', COALESCE(NEW.chunk_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Decision 6: Hybrid Search with Reciprocal Rank Fusion

**What**: Combine BM25 document search and chunk-level vector search using RRF, with injected strategies for both BM25 and embedding.

**Why**:
- RRF is scale-independent — works regardless of score ranges from different methods
- Documents ranking highly in multiple methods get boosted
- No complex score normalization required
- Configurable k parameter controls rank decay

**RRF Formula**: `score = Σ(weight_i / (k + rank_i))` where k=60 is typical.

**Hybrid flow**:
1. BM25 search returns candidate chunks (ranked by keyword relevance)
2. Vector search returns candidate chunks (ranked by semantic similarity)
3. RRF combines chunk rankings using weighted formula
4. **Optional**: Cross-encoder reranks top-K RRF results (if `SEARCH_RERANK_ENABLED=true`)
5. Chunks are aggregated to document level: group by `content_id`, document score = max chunk score, tiebreak by chunk_id
6. Results include up to 3 best-matching chunks per document, with matching terms highlighted using `<mark>` HTML tags

**Implementation**:

```python
class HybridSearchService:
    def __init__(
        self,
        session: Session,
        bm25_strategy: BM25SearchStrategy | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.session = session
        self.bm25_strategy = bm25_strategy or get_bm25_strategy(session)
        self.embedding_provider = embedding_provider or get_embedding_provider()

    async def search(self, query: str, ...) -> list[SearchResult]:
        # Run BM25 and vector search in parallel
        bm25_results, vector_results = await asyncio.gather(
            self.bm25_strategy.search(query, search_limit),
            self._vector_search(query, search_limit),
        )
        # Calculate weighted RRF scores and aggregate to documents
        ...
```

### Decision 7: Cross-Encoder Reranking

**What**: An optional reranking step after RRF fusion that uses a cross-encoder or fast LLM to score (query, chunk_text) pairs for improved result quality. Disabled by default.

**Why**:
- Bi-encoder embeddings (used in vector search) encode query and document independently — cross-encoders jointly encode (query, document) for much higher relevance accuracy
- RRF produces good results but a cross-encoder can significantly improve the top-10 ranking quality
- SLMs and fast LLMs (Gemini Flash, Claude Haiku) are now fast enough for practical reranking
- Making it optional means zero latency impact when not needed

**Supported providers**:

| Provider | Model | Latency | Cost | Quality |
|----------|-------|---------|------|---------|
| Cohere Rerank | rerank-english-v3.0 | ~100ms/50 docs | $0.002/search | High |
| Jina Rerank | jina-reranker-v2-base | ~150ms/50 docs | $0.002/search | High |
| Local | ms-marco-MiniLM-L-12-v2 | ~200ms/50 docs | Free | Medium |
| LLM | Gemini Flash / Claude Haiku | ~500ms/50 docs | ~$0.01/search | Very High |

**Implementation**:

```python
# src/services/reranking.py
class RerankProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """
        Rerank documents against query.
        Returns list of (original_index, relevance_score) sorted by relevance.
        """
        ...

class CohereRerankProvider:
    async def rerank(self, query, documents, top_k=None):
        response = await self._client.rerank(
            query=query, documents=documents,
            model=self.model, top_n=top_k,
        )
        return [(r.index, r.relevance_score) for r in response.results]

class LLMRerankProvider:
    """Uses the project's LLM router with a fast model (e.g., gemini-2.5-flash, claude-haiku-4-5)."""
    async def rerank(self, query, documents, top_k=None):
        # Uses existing LLM router (src/services/llm_router.py) — model configurable via SEARCH_RERANK_MODEL
        # Structured prompt: "Rate relevance of document to query on 0-10 scale"
        # Batch scoring with concurrent requests
        ...
```

**Trade-offs**:
- Adds latency (100-500ms depending on provider)
- Adds cost per search request
- Only worth it for top-K results (50 is a good default)
- Disabled by default — users opt in when quality matters more than speed

### Decision 8: Search API Design

**What**: RESTful API with flexible query options and rich metadata for both human UIs and programmatic agent consumption.

**Endpoints**:
- `GET /api/v1/search?q=...&type=hybrid&limit=20` — Simple searches
- `POST /api/v1/search` — Complex searches with filters and weights
- `GET /api/v1/search/chunks/{chunk_id}` — Chunk detail retrieval

**Response structure**:

```json
{
  "results": [
    {
      "id": 123,
      "type": "content",
      "title": "AI Weekly: Transformer Advances",
      "score": 0.89,
      "scores": {"bm25": 0.85, "vector": 0.92, "rrf": 0.89},
      "source": "GMAIL",
      "published_date": "2024-06-15",
      "matching_chunks": [
        {
          "chunk_id": 456,
          "content": "The new attention mechanism...",
          "section": "Technical Deep-Dive",
          "score": 0.94,
          "highlight": "The new <mark>attention mechanism</mark> reduces...",
          "deep_link": "https://youtube.com/watch?v=xxx&t=145",
          "chunk_type": "paragraph"
        }
      ]
    }
  ],
  "total": 156,
  "meta": {
    "bm25_strategy": "paradedb_bm25",
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small",
    "rerank_provider": "cohere",
    "rerank_model": "rerank-english-v3.0",
    "query_time_ms": 85,
    "backend": "local"
  }
}
```

**Design rationale for `meta` object**: The metadata enables programmatic agents to reason about search quality (e.g., a Deep Research Agent can note that results came from native FTS and adjust its confidence accordingly). It also helps debug search quality issues in production.

### Decision 9: Ingestion Integration and Backfill

**What**: Integrate chunking and embedding at ingest time (non-blocking, feature-flagged), with a backfill command for existing documents.

**Why**:
- New documents should be searchable without manual intervention
- Existing documents need a one-time migration
- Chunking/embedding failures must not block content ingestion

**At-ingest flow** (synchronous, best-effort):
1. Content is ingested and committed to the database (existing flow completes first)
2. If `ENABLE_SEARCH_INDEXING=true`: ChunkingService chunks the content
3. EmbeddingProvider generates embeddings for chunks
4. Chunks stored in `document_chunks` in a separate transaction
5. On chunking failure: log error with content_id, content remains without chunks (searchable via BM25 on title only)
6. On embedding failure: log error, store chunks without embeddings (BM25 search works, vector search skips this content)
7. Failures do NOT rollback the content ingestion — the content is always preserved

**Backfill command** (`python -m src.scripts.backfill_chunks`):
- Identifies documents without chunks
- Re-parses with appropriate parser
- Chunks and embeds in batches
- Supports resume after interruption (tracks last processed content_id)
- Rate-limits embedding API calls
- Reports progress (processed/total, chunks created, ETA)
- Supports dry-run mode

### Decision 10: Source-Configurable Chunking Strategy

**What**: Allow per-source override of chunking parameters (chunk size, overlap, and strategy) via the existing `sources.d/` YAML configuration, using the established cascading defaults pattern.

**Why**:
- Different content sources have different characteristics — a long-form podcast transcript benefits from larger chunks (1024 tokens) while a short RSS newsletter may do better with smaller chunks (256 tokens)
- YouTube transcripts have natural 30-second windows that may be too short for some channels and too long for others
- The `sources.d/` cascading defaults already support per-type and per-entry overrides — extending to chunking is zero new infrastructure
- Enables experimentation with chunking parameters per source without affecting the global default

**Implementation**:

```python
# src/config/sources.py — Add to SourceDefaults
class SourceDefaults(BaseModel):
    # ... existing fields ...
    chunk_size_tokens: int | None = None       # Override CHUNK_SIZE_TOKENS
    chunk_overlap_tokens: int | None = None    # Override CHUNK_OVERLAP_TOKENS
    chunking_strategy: str | None = None       # Force: structured, youtube, markdown, section
```

```yaml
# sources.d/podcasts.yaml — Example: larger chunks for podcasts
defaults:
  type: podcast
  chunk_size_tokens: 1024
  chunk_overlap_tokens: 128
sources:
- name: Lex Fridman
  url: https://lexfridman.com/feed/podcast
  chunk_size_tokens: 2048    # Even larger for very long episodes
```

**Resolution flow in ChunkingService**:
1. Look up the source config entry for the content being chunked (via `Content.source_url` or `Content.source_type`)
2. If source entry has `chunking_strategy` override → use that strategy instead of auto-detecting from `parser_used`
3. If source entry has `chunk_size_tokens` / `chunk_overlap_tokens` → use those values
4. Otherwise → fall back to global `Settings.chunk_size_tokens` / `Settings.chunk_overlap_tokens`
5. Strategy auto-detection from `parser_used` remains the default when no override is specified

**Valid `chunking_strategy` values**: `structured` (DoclingParser-style), `youtube` (timestamp-based), `markdown` (heading-based), `section` (summary/digest-style)

**Alternatives considered**:
- Store chunking config in the database per-content: More complex, harder to audit, no cascading defaults
- Separate chunking config file: Fragments configuration; sources.d already has the right abstraction
- Per-parser config only: Doesn't allow per-feed tuning within the same parser type

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| pg_search unavailable on Neon | Lower search quality | Native FTS fallback, document quality difference |
| Embedding cost at scale | Higher ingestion costs | Batch embedding, local model option, feature flag |
| Index size growth | Disk usage, slower backups | Monitor size, partial indexes, chunk limits |
| Native FTS quality < BM25 | Lower relevance on Neon | Document clearly, recommend pg_search for production |
| Embedding dimension mismatch | Can't switch providers freely | Require re-indexing on dimension change |
| Chunk proliferation | 10-50x rows per document | Index optimization, chunk size tuning |
| Parser output changes | Chunking depends on format | Abstract interface, version tracking |
| Local model memory usage | High RAM for sentence-transformers | Document requirements, recommend cloud for limited resources |

## Migration Plan

1. **Phase 1**: Database schema (non-breaking)
   - Enable pgvector extension (if not already)
   - Create `document_chunks` table with embedding + search_vector columns
   - Create TSVECTOR trigger and GIN index
   - Create HNSW index on embedding column
   - Conditionally create BM25 index (if pg_search available)

2. **Phase 2**: Core services
   - BM25 strategy protocol + implementations + factory
   - Embedding provider protocol + implementations + factory
   - Chunking service with parser-aware strategies

3. **Phase 3**: Search service and API
   - HybridSearchService with injected strategies
   - Search API endpoints with metadata

4. **Phase 4**: Integration
   - Ingestion pipeline integration (feature-flagged)
   - Backfill command for existing documents

5. **Rollback**: Drop `document_chunks` table, remove indexes and triggers

## Resolved Questions

1. **Store raw chunk text separately from embeddings for BM25 on chunks?** — Yes: `chunk_text` column for ParadeDB BM25, `search_vector` TSVECTOR column for native FTS. Both coexist.
2. **YouTube chunk at TranscriptSegment or paragraph level?** — 30-second timestamp windows (natural speech units), matching existing YouTubeParser output.
3. **Cohere `search_query` input_type for query embeddings?** — Yes, handled internally by `CohereEmbeddingProvider`.
4. **Expose BM25 strategy name in response metadata?** — Yes, in `meta.bm25_strategy`.
5. **Vector search highlighting strategy?** — Highlight based on original query *terms* (keyword matching) in all chunk results, regardless of whether the chunk was found via BM25 or vector search. For vector-only results where no query terms appear literally, the `highlight` field is set to the first 200 characters of `chunk_text` (no `<mark>` tags). This is the standard approach used by hybrid search systems (Vespa, Weaviate).
6. **Backfill: re-parse from raw source or markdown_content?** — Re-chunk from existing `Content.markdown_content` only. The unified model already stores parsed markdown; parsers already ran at ingest time. Backfill does NOT re-fetch raw source or re-run parsers — it only runs the chunking + embedding pipeline on existing markdown.
7. **Do we chunk original Content or Digest summaries? Or both?** — Both. `document_chunks.content_id` references `contents.id`. Digests and summaries that are stored as Content records get chunked like any other content. The `_chunk_section_markdown()` strategy handles their `## Section` structure.
8. **Boolean query syntax across backends?** — Normalize to simple terms. Both strategies receive the raw query string; `PostgresNativeFTSStrategy` uses `plainto_tsquery()` which strips operators, `ParadeDBBM25Strategy` passes the query directly to `@@@`. This means Neon users lose Boolean operators (AND/OR/NOT) — this is a documented quality tradeoff, not a bug.
9. **Protocol mockability for testing?** — Use `typing.Protocol` (not ABC). Protocols are structurally typed — any class matching the method signatures satisfies the protocol. Tests use concrete mock classes (not `unittest.mock.Mock`) to ensure type safety. Mark protocols with `@runtime_checkable` for isinstance checks in factories.

## Open Questions

1. How do we handle re-chunking when parser logic changes? (version chunks vs. full regeneration — deferred to future proposal)
2. Should we cache frequent query embeddings to reduce API costs? (deferred — measure actual costs first)
3. Should we support query-time embedding provider override for A/B testing? (deferred — not needed for MVP)
