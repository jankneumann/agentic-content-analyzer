# Document Search

Hybrid BM25 + vector search across all ingested content with Reciprocal Rank Fusion (RRF).

## Architecture

```
Query → [BM25 Strategy] ──→ RRF Fusion → [Reranking] → Document Aggregation → Response
      → [Vector Search]  ──↗            (optional)
```

**Components:**
- **BM25 Strategy**: ParadeDB pg_search (default) or PostgreSQL native FTS (fallback)
- **Embedding Provider**: OpenAI, Voyage AI, Cohere, or local sentence-transformers
- **RRF Fusion**: Weighted reciprocal rank fusion (scale-independent)
- **Reranking**: Optional cross-encoder pass (Cohere, Jina, local, or LLM-based)
- **Chunking Service**: 5 content-aware strategies with per-source overrides

## Backend Compatibility

| Extension | Local | Supabase | Neon | Railway |
|-----------|-------|----------|------|---------|
| pgvector | Install | Built-in | Built-in | Built-in |
| pg_search | Install | Available | Available (AWS) | Built-in |
| Native FTS | Built-in | Built-in | Built-in | Built-in |

## Search Types

- **`hybrid`** (default): Combines BM25 + vector search via RRF
- **`bm25`**: Keyword-only search (no embeddings needed)
- **`vector`**: Semantic-only search (embedding similarity)

## API Endpoints

### Simple Search (GET)

```bash
curl "http://localhost:8000/api/v1/search?q=transformer+architecture&limit=10"
```

Query params: `q`, `type`, `limit`, `offset`, `source_type`, `date_from`, `date_to`, `publication`

### Advanced Search (POST)

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "transformer architecture",
    "type": "hybrid",
    "filters": {
      "source_types": ["rss", "gmail"],
      "date_from": "2024-01-01T00:00:00Z",
      "chunk_types": ["paragraph", "table"]
    },
    "bm25_weight": 0.6,
    "vector_weight": 0.4,
    "limit": 20
  }'
```

### Chunk Detail

```bash
curl http://localhost:8000/api/v1/search/chunks/42
```

## Configuration

### Embedding Providers

| Provider | Model | Dimensions | Max Tokens | Cost |
|----------|-------|-----------|------------|------|
| `local` (default) | all-MiniLM-L6-v2 | 384 | 256 | Free |
| `openai` | text-embedding-3-small | 1536 | 8191 | $0.02/1M |
| `voyage` | voyage-3 | 1024 | 32000 | $0.06/1M |
| `cohere` | embed-english-v3.0 | 1024 | 512 | $0.10/1M |

```bash
# .env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

### Reranking (Optional)

Disabled by default. Enable for higher quality results at the cost of latency.

```bash
SEARCH_RERANK_ENABLED=true
SEARCH_RERANK_PROVIDER=cohere  # cohere, jina, local, llm
SEARCH_RERANK_MODEL=rerank-english-v3.0
SEARCH_RERANK_TOP_K=50
```

### Search Weights

```bash
SEARCH_BM25_WEIGHT=0.5     # Keyword relevance weight
SEARCH_VECTOR_WEIGHT=0.5   # Semantic similarity weight
SEARCH_RRF_K=60             # RRF rank decay parameter
SEARCH_DEFAULT_LIMIT=20
SEARCH_MAX_LIMIT=100
```

### BM25 Strategy

```bash
SEARCH_BM25_STRATEGY=auto   # auto, paradedb, native
```

### Chunking

Global defaults (overridable per-source in `sources.d/`):

```bash
CHUNK_SIZE_TOKENS=512
CHUNK_OVERLAP_TOKENS=64
ENABLE_SEARCH_INDEXING=true
```

Per-source override in `sources.d/youtube_playlist.yaml`:

```yaml
sources:
  - id: PLxxxxxx
    name: "My Playlist"
    chunk_size_tokens: 1024
    chunking_strategy: gemini_summary
```

## Chunking Strategies

| Strategy | Auto-detected from | Content Type |
|----------|-------------------|--------------|
| `structured` | DoclingParser | PDFs, DOCX with headings/tables |
| `youtube_transcript` | youtube_transcript_api | Timestamped transcripts |
| `gemini_summary` | gemini | Gemini video summaries |
| `markdown` (default) | MarkItDownParser | General markdown content |
| `section` | (manual) | Summaries and digests |

## Backfill

Index existing content that was ingested before search was enabled:

```bash
# Full backfill
aca manage backfill-chunks

# Dry run
aca manage backfill-chunks --dry-run

# Fill missing embeddings only
aca manage backfill-chunks --embed-only

# Specific content
aca manage backfill-chunks --content-id 42

# Rate limiting
aca manage backfill-chunks --batch-size 50 --delay 2.0
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No search results | Run `aca manage backfill-chunks` to index existing content |
| Slow vector search | Check `EMBEDDING_DIMENSIONS` matches model; HNSW index only helps at scale |
| "Unknown embedding provider" | Install optional deps: `pip install ".[embeddings]"` |
| pg_search not detected | Check `SELECT * FROM pg_extension WHERE extname = 'pg_search'` |
| Embedding API rate limits | Increase `--delay` in backfill; reduce `--batch-size` |
| Changing embedding provider | Different providers have different dimensions. You must: 1) `ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(N)` where N is the new dimension, 2) Re-run backfill with `--embed-only` to regenerate all embeddings |
| Migration uses vector(384) | The migration creates the column with 384 dimensions (matching local provider). For production with OpenAI (1536), alter the column before backfilling |
