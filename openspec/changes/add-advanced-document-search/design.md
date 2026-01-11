# Design: Advanced Document Search

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
-- Create BM25 index
CREATE INDEX idx_newsletters_search ON newsletters
USING bm25 (id, title, raw_text, sender, publication)
WITH (key_field='id');

-- Search with scoring
SELECT id, title, pdb.score(id) as relevance
FROM newsletters
WHERE raw_text @@@ 'machine learning transformers'
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
```

### Decision 5: Searchable Content Fields

**What**: Index and embed specific fields for search:

| Table | BM25 Fields | Embedding Source |
|-------|-------------|------------------|
| newsletters | title, raw_text, sender, publication | title + first 8000 chars of raw_text |
| newsletter_summaries | executive_summary, key_themes (JSON→text), strategic_insights | executive_summary + key_themes |
| documents | filename, markdown_content | markdown_content (truncated) |
| digests | title, executive_overview, strategic_insights | executive_overview |

**Why**: Balance between comprehensive search and index/embedding size

### Decision 6: Search API Design

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

## Migration Plan

1. **Phase 1**: Add extensions and columns (non-breaking)
   - Enable pg_search and pgvector extensions
   - Add embedding column to newsletters (nullable)
   - Create BM25 index on existing content

2. **Phase 2**: Backfill embeddings
   - Background job to generate embeddings for existing content
   - Rate-limited to avoid API throttling
   - Track progress in migration state table

3. **Phase 3**: Enable hybrid search API
   - New endpoints, existing endpoints unchanged
   - Feature flag for gradual rollout

4. **Rollback**: Drop indexes and columns, disable extensions

## Open Questions

1. Should we support cross-encoder reranking as a third stage for top results?
2. Should embeddings be stored in a separate table for flexibility?
3. What's the maximum document length before truncation for embeddings?
4. Should we cache frequent queries?
