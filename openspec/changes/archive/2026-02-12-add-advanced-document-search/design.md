# Design: Advanced Document Search

## Prerequisites

This design assumes the **refactor-unified-content-model** change is complete:
- Single `contents` table replaces Newsletter + Document
- All content stored as markdown in `Content.markdown_content`
- Summaries and digests use markdown with section conventions

## Context

The newsletter aggregator ingests content from multiple sources (Gmail, RSS, file uploads, YouTube) and stores it in PostgreSQL. Users need to search across this content efficiently using natural language queries. The current ILIKE search on titles is insufficient for:

- Finding content by concepts/topics rather than exact keywords
- Searching across full document content
- Ranking results by relevance
- Handling synonyms and semantic similarity

**Stakeholders**: End users searching for content, API consumers, digest generation (finding related historical content)

**Constraints**:
- Must work with existing PostgreSQL infrastructure (Docker Compose setup)
- Should not require external search services (Elasticsearch, Typesense)
- Embedding generation adds latency and cost at ingestion time
- Must handle incremental updates (new documents added continuously)

## Goals / Non-Goals

**Goals**:
- Full-text search across all document content with BM25 relevance scoring
- Semantic search using embeddings for conceptual matching
- Hybrid search combining both approaches with configurable weighting
- Sub-second search latency for typical queries
- Automatic index updates on document insertion/update
- Filtering by source, date range, publication, status
- Search across newsletters, summaries, documents, and themes

**Non-Goals**:
- Real-time search (within milliseconds of ingestion) - slight delay acceptable
- Federated search across Neo4j knowledge graph (separate capability)
- Query suggestions/autocomplete (future enhancement)
- Search analytics and query logging (future enhancement)
- Multi-language search (English-only initially)

## Decisions

### Decision 1: Use pg_search (ParadeDB) for BM25 Full-Text Search

**What**: Use the pg_search extension rather than PostgreSQL's built-in `tsvector`/`tsquery` or external search services.

**Why**:
- BM25 provides better relevance ranking than PostgreSQL's native FTS
- Native PostgreSQL extension = no external service to maintain
- Real-time index updates on INSERT/UPDATE/DELETE
- Supports complex queries with field boosting
- ParadeDB is production-ready and actively maintained

**Alternatives considered**:
- PostgreSQL native FTS (`tsvector`/`tsquery`): Lower quality ranking, no BM25
- Elasticsearch: External service complexity, data sync challenges
- Typesense: External service, additional infrastructure
- pg_trgm (trigram): Good for fuzzy matching but no semantic ranking

**Syntax**:
```sql
-- Create BM25 index on unified Content table
CREATE INDEX idx_contents_search ON contents
USING bm25 (id, title, markdown_content, author, publication)
WITH (key_field='id');

-- Search with scoring
SELECT id, title, pdb.score(id) as relevance
FROM contents
WHERE markdown_content @@@ 'machine learning transformers'
ORDER BY relevance DESC
LIMIT 20;
```

### Decision 2: Use pgvector for Embedding Storage and Similarity Search

**What**: Store document embeddings using pgvector extension and use vector similarity operators for semantic search.

**Why**:
- Native PostgreSQL extension, same transaction guarantees
- IVFFlat and HNSW index types for fast approximate nearest neighbor
- Works alongside pg_search for hybrid queries
- Supports cosine similarity, L2 distance, inner product

**Vector dimensions**: 1536 (OpenAI text-embedding-3-small) or 384 (local alternatives like all-MiniLM-L6-v2)

**Syntax**:
```sql
-- Add vector column
ALTER TABLE newsletters ADD COLUMN embedding vector(1536);

-- Create HNSW index for fast similarity search
CREATE INDEX idx_newsletters_embedding ON newsletters
USING hnsw (embedding vector_cosine_ops);

-- Similarity search
SELECT id, title, 1 - (embedding <=> query_embedding) as similarity
FROM newsletters
ORDER BY embedding <=> query_embedding
LIMIT 20;
```

### Decision 3: Reciprocal Rank Fusion (RRF) for Hybrid Search

**What**: Combine BM25 and vector search results using RRF rather than score normalization or simple weighting.

**Why**:
- Scale-independent: Works regardless of score ranges from different methods
- Robust: Documents ranking highly in multiple methods get boosted
- Simple: No complex score normalization required
- Configurable: k parameter controls rank decay

**RRF Formula**: `score = sum(1 / (k + rank_i))` where k=60 is typical

**Implementation**:
```sql
WITH bm25_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY pdb.score(id) DESC) as rank_bm25
    FROM newsletters
    WHERE raw_text @@@ 'search query'
    LIMIT 100
),
vector_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> query_vec) as rank_vec
    FROM newsletters
    ORDER BY embedding <=> query_vec
    LIMIT 100
),
combined AS (
    SELECT COALESCE(b.id, v.id) as id,
           COALESCE(1.0 / (60 + b.rank_bm25), 0) as rrf_bm25,
           COALESCE(1.0 / (60 + v.rank_vec), 0) as rrf_vec
    FROM bm25_results b
    FULL OUTER JOIN vector_results v ON b.id = v.id
)
SELECT id, (rrf_bm25 + rrf_vec) as rrf_score
FROM combined
ORDER BY rrf_score DESC
LIMIT 20;
```

### Decision 4: Embedding Model Selection

**What**: Use OpenAI text-embedding-3-small as default, with support for local models.

**Why**:
- text-embedding-3-small: Good quality, low cost ($0.02/1M tokens), 1536 dimensions
- Already have OpenAI integration for Graphiti
- Can add local models (sentence-transformers) later for cost/privacy

**Configuration**:
```python
# settings.py
EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_PROVIDER: str = "openai"  # or "local"
EMBEDDING_DIMENSIONS: int = 1536
CHUNK_SIZE_TOKENS: int = 512  # Target chunk size
CHUNK_OVERLAP_TOKENS: int = 64  # Overlap between chunks
```

### Decision 5: Semantic Chunking with Parser Integration

**What**: Chunk documents into semantically meaningful units that leverage the existing advanced document parsing capabilities (Docling, YouTube, MarkItDown).

**Why**:
- Embedding entire documents loses semantic precision for long content
- The parsers already extract rich structural information we should leverage
- Chunk-level search enables precise snippet highlighting and navigation
- YouTube timestamps enable deep-linking to exact video moments
- Tables and sections are natural semantic boundaries

**Chunking Strategy by Source**:

With the unified Content model, all content is markdown. Chunking strategy is determined by `parser_used`:

| Parser | Chunking Approach | Boundaries | Metadata Preserved |
|--------|-------------------|------------|-------------------|
| **DoclingParser** | Section + paragraph | Headings (H1-H6), page breaks, table boundaries | Page number, section title, table caption |
| **YouTubeParser** | Timestamp segments | 30-second windows with sentence boundaries | Video timestamp, deep-link URL |
| **MarkItDownParser** | Markdown structure | Headings, list boundaries, code blocks | Section path (e.g., "# Intro > ## Setup") |
| **Default** (Gmail, RSS) | Heading-based | H1/H2/H3 boundaries, paragraphs | Publication, author |
| **Summaries/Digests** | Section headers | `## Executive Summary`, `## Key Themes`, etc. | Section type, theme tags |

**Chunk Model**:
```python
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: int  # Primary key

    # Source reference (simplified with unified Content model)
    content_id: int  # FK to contents table
    source_type: str  # "content", "summary", "digest" (for summaries/digests that also get chunked)

    # Chunk content
    chunk_text: str  # Text content of the chunk
    chunk_index: int  # Order within document (0, 1, 2...)

    # Structural metadata
    section_path: str | None  # "# Heading > ## Subheading"
    heading_text: str | None  # Nearest heading above chunk
    chunk_type: str  # "paragraph", "table", "code", "quote", "transcript"

    # Location anchors
    page_number: int | None  # For PDFs
    start_char: int | None  # Character offset in source
    end_char: int | None
    timestamp_start: float | None  # For YouTube (seconds)
    timestamp_end: float | None
    deep_link_url: str | None  # Direct link to chunk location

    # Embedding
    embedding: Vector(1536)  # pgvector column

    # Timestamps
    created_at: datetime
```

**Chunking Algorithm**:
```python
class ChunkingService:
    def chunk_document(self, content: DocumentContent) -> list[DocumentChunk]:
        """Route to appropriate chunker based on parser_used."""
        if content.parser_used == "DoclingParser":
            return self._chunk_structured_document(content)
        elif content.parser_used == "YouTubeParser":
            return self._chunk_youtube_transcript(content)
        else:
            return self._chunk_markdown(content)

    def _chunk_structured_document(self, content: DocumentContent) -> list[DocumentChunk]:
        """Use Docling's structural output for boundaries."""
        chunks = []
        # 1. Extract headings hierarchy from markdown
        # 2. Split on heading boundaries
        # 3. Handle tables as separate chunks with full context
        # 4. Respect page boundaries from metadata
        # 5. Split large sections at paragraph boundaries
        return chunks

    def _chunk_youtube_transcript(self, content: DocumentContent) -> list[DocumentChunk]:
        """Leverage existing YouTubeTranscript segment structure."""
        # 1. Parse existing timestamped paragraphs from markdown
        # 2. Each paragraph becomes a chunk with timestamp metadata
        # 3. Include deep-link URL for each chunk
        # 4. Preserve 30-second window groupings
        return chunks

    def _chunk_markdown(self, content: DocumentContent) -> list[DocumentChunk]:
        """Fallback: heading-based + size-based splitting."""
        # 1. Split on H1/H2/H3 headings
        # 2. Further split large sections by paragraph
        # 3. Keep code blocks together
        # 4. Track section path for each chunk
        return chunks
```

**Table Handling**:
Tables from DoclingParser are chunked specially:
- Each table becomes its own chunk with `chunk_type="table"`
- Caption and headers are prepended as context
- Full markdown representation preserved
- Enables search like "table showing benchmark results"

**Chunk Size Targets**:
- Target: ~512 tokens per chunk
- Overlap: ~64 tokens between consecutive chunks (for context continuity)
- Tables: Kept whole even if exceeding target (up to 2048 tokens)
- YouTube segments: Grouped to ~30 seconds (natural speech units)

### Decision 6: Searchable Content Fields (Updated for Chunks)

**What**: Index documents at both document-level (BM25) and chunk-level (embeddings):

| Level | Search Type | Content | Use Case |
|-------|-------------|---------|----------|
| **Document** | BM25 | Full text (title, raw_text, sender) | Keyword search, filtering |
| **Chunk** | Vector | Semantic chunks with metadata | Semantic search, precise highlighting |

**Hybrid Flow**:
1. BM25 search returns candidate documents
2. Vector search returns matching chunks
3. RRF combines document scores with chunk scores
4. Results show document with best-matching chunk highlighted

**Search Response Enhancement**:
```json
{
  "results": [
    {
      "id": 123,
      "type": "newsletter",
      "title": "AI Weekly: Transformer Advances",
      "score": 0.89,
      "matching_chunks": [
        {
          "chunk_id": 456,
          "content": "The new attention mechanism...",
          "section": "Technical Deep-Dive",
          "score": 0.94,
          "highlight": "The new <mark>attention mechanism</mark> reduces...",
          "deep_link": "https://youtube.com/watch?v=xxx&t=145"
        }
      ]
    }
  ]
}
```

### Decision 7: Search API Design

**What**: RESTful API with flexible query options:

```
GET /api/v1/search?q=transformer%20models&type=hybrid&limit=20
POST /api/v1/search
{
  "query": "transformer models",
  "type": "hybrid",  // bm25, vector, hybrid
  "weights": {"bm25": 0.5, "vector": 0.5},
  "filters": {
    "sources": ["GMAIL", "RSS"],
    "date_from": "2024-01-01",
    "date_to": "2024-12-31",
    "publications": ["AI Weekly"]
  },
  "limit": 20,
  "offset": 0,
  "include": ["summaries", "highlights"]
}
```

**Response**:
```json
{
  "results": [
    {
      "id": 123,
      "type": "newsletter",
      "title": "...",
      "snippet": "...highlighted match...",
      "score": 0.89,
      "scores": {"bm25": 0.85, "vector": 0.92, "rrf": 0.89},
      "source": "GMAIL",
      "published_date": "2024-06-15",
      "summary": {...}  // if include=summaries
    }
  ],
  "total": 156,
  "query_time_ms": 45
}
```

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| pg_search not available in managed PostgreSQL | Can't use BM25 | Fallback to native FTS, document Dockerfile setup |
| Embedding cost at scale | Higher ingestion costs | Batch embedding, local model option, embed on-demand |
| Index size growth | Disk usage, slower backups | Monitor size, consider partial indexes |
| Cold start latency | First search slow | Warm indexes on startup, connection pooling |
| Query complexity | Hard to debug | Logging, query explain, monitoring |
| Chunk proliferation | Many chunks per document (10-50x) | Index optimization, chunk size tuning, lazy loading |
| Chunking consistency | Re-chunking changes IDs | Version chunks, track chunk hash for dedup |
| Parser output changes | Chunking depends on parser format | Abstract chunking interface, parser version tracking |

## Migration Plan

1. **Phase 1**: Add extensions and schema (non-breaking)
   - Enable pg_search and pgvector extensions
   - Create `document_chunks` table with embedding column
   - Create BM25 indexes on source tables

2. **Phase 2**: Implement chunking service
   - ChunkingService with parser-aware strategies
   - Integration with DocumentContent model
   - Unit tests for each chunking strategy

3. **Phase 3**: Backfill chunks and embeddings
   - Process existing newsletters, documents, summaries
   - Batch embedding generation with rate limiting
   - Track progress, support resume after interruption

4. **Phase 4**: Enable hybrid search API
   - New endpoints, existing endpoints unchanged
   - Feature flag for gradual rollout
   - Chunk-level results with document aggregation

5. **Rollback**: Drop `document_chunks` table, remove indexes

## Open Questions

1. Should we support cross-encoder reranking as a third stage for top results?
2. Should we store raw chunk text separately from embeddings for BM25 on chunks?
3. How do we handle re-chunking when parser logic changes? (versioning vs. regeneration)
4. Should we cache frequent queries or embedding computations?
5. For YouTube, should we chunk at the TranscriptSegment level or the paragraph level?
