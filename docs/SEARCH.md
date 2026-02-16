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

## Switching Embedding Providers

The `switch-embeddings` command safely migrates from one embedding provider to another. It handles clearing old embeddings, rebuilding the HNSW index, and optionally re-embedding all content.

```bash
# Preview what would happen
aca manage switch-embeddings --dry-run

# Switch to OpenAI (with automatic backfill)
aca manage switch-embeddings --provider openai --model text-embedding-3-small

# Switch without backfill (schedule overnight)
aca manage switch-embeddings --provider voyage --model voyage-3 --skip-backfill

# Skip confirmation prompt
aca manage switch-embeddings --yes

# Custom batch size and rate limiting
aca manage switch-embeddings --batch-size 50 --delay 2.0
```

**What happens during a switch:**
1. Validates the target provider can be instantiated
2. NULLs all existing embeddings and metadata
3. Drops and recreates the HNSW index
4. Optionally triggers a backfill with the new provider

**Impact:** Vector search is unavailable during the switch until backfill completes. BM25 keyword search continues working throughout.

**Duration estimates:**
- Clearing embeddings: seconds (single UPDATE)
- Index rebuild: seconds
- Backfill: ~1-5 minutes per 1000 chunks (depends on provider API speed)

**Embedding metadata tracking:** Each chunk records which provider/model generated its embedding (`embedding_provider`, `embedding_model` columns). A startup check warns if the configured provider doesn't match what's in the database.

**Advanced local models:**

For instruction-tuned models like `gte-Qwen2-1.5B-instruct`:

```bash
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=Alibaba-NLP/gte-Qwen2-1.5B-instruct
EMBEDDING_TRUST_REMOTE_CODE=true
EMBEDDING_MAX_SEQ_LENGTH=8192  # Optional: override model default
```

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
| Changing embedding provider | Use `aca manage switch-embeddings` — handles clearing, index rebuild, and backfill |
| Config mismatch warning at startup | Means DB embeddings are from a different provider than configured. Run `aca manage switch-embeddings` to normalize |
| Mixed providers in DB | Multiple providers wrote embeddings. Run `aca manage switch-embeddings` to normalize to one provider |
