# Design: Cross-Backend Hybrid Search with RRF

## Context

The newsletter aggregator supports three PostgreSQL backends: local PostgreSQL, Supabase, and Neon. Each has different extension availability:

- **pgvector**: Available on all three (vector similarity search)
- **pg_search (ParadeDB)**: Available on local and Supabase, **not on Neon**
- **PostgreSQL Native FTS**: Built into PostgreSQL core, available everywhere

The `add-advanced-document-search` proposal assumes pg_search for BM25. This design adds a provider-aware abstraction layer that maintains API consistency while adapting to backend capabilities.

**Stakeholders**: Developers deploying to different backends, DevOps managing infrastructure, users searching content

**Constraints**:
- Must work identically across all three backends from an API perspective
- Cannot require pg_search on Neon (not available)
- Should prefer higher-quality search when available
- Embedding provider must be configurable without code changes

## Goals / Non-Goals

**Goals**:
- Provider-aware BM25 strategy with automatic backend detection
- Pluggable embedding providers with configuration-based selection
- Identical search API regardless of backend
- Graceful degradation (use best available search method)
- Clear performance characteristics per backend

**Non-Goals**:
- Achieving identical search quality across backends (native FTS < BM25)
- Supporting non-PostgreSQL databases
- Real-time embedding model switching (requires re-indexing)

## Decisions

### Decision 1: BM25 Strategy Protocol Pattern

**What**: Define a `BM25SearchStrategy` protocol with multiple implementations, selected at runtime based on database backend.

**Why**:
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
    def name(self) -> str:
        """Strategy identifier for logging/debugging."""
        ...

    async def search(
        self,
        query: str,
        limit: int = 100,
        source_types: list[str] | None = None,
    ) -> list[tuple[int, int]]:
        """
        Execute keyword search.

        Returns:
            List of (chunk_id, rank) tuples, where rank is 1-indexed position.
        """
        ...

    def get_required_columns(self) -> list[str]:
        """Return columns this strategy requires (for schema validation)."""
        ...


class PostgresNativeFTSStrategy:
    """Uses PostgreSQL native full-text search with ts_rank_cd."""

    name = "postgres_native_fts"

    def __init__(self, session: Session):
        self.session = session

    async def search(
        self,
        query: str,
        limit: int = 100,
        source_types: list[str] | None = None,
    ) -> list[tuple[int, int]]:
        # Build base query
        stmt = text("""
            SELECT id, ts_rank_cd(search_vector, plainto_tsquery('english', :query)) as rank
            FROM document_chunks
            WHERE search_vector @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        result = self.session.execute(stmt, {"query": query, "limit": limit})
        return [(row.id, idx + 1) for idx, row in enumerate(result.fetchall())]

    def get_required_columns(self) -> list[str]:
        return ["search_vector"]


class ParadeDBBM25Strategy:
    """Uses pg_search extension for true BM25 ranking."""

    name = "paradedb_bm25"

    def __init__(self, session: Session):
        self.session = session

    async def search(
        self,
        query: str,
        limit: int = 100,
        source_types: list[str] | None = None,
    ) -> list[tuple[int, int]]:
        stmt = text("""
            SELECT id, paradedb.score(id) as score
            FROM document_chunks
            WHERE chunk_text @@@ :query
            ORDER BY score DESC
            LIMIT :limit
        """)

        result = self.session.execute(stmt, {"query": query, "limit": limit})
        return [(row.id, idx + 1) for idx, row in enumerate(result.fetchall())]

    def get_required_columns(self) -> list[str]:
        return []  # Uses chunk_text directly
```

**Alternatives considered**:
- Single implementation with feature flags: Less testable, harder to extend
- Separate search services per backend: Code duplication, harder to maintain

### Decision 2: Backend Detection for Strategy Selection

**What**: Extend the existing provider factory to detect available extensions and select the best BM25 strategy.

**Why**:
- Reuses existing provider detection infrastructure
- Centralizes backend capability detection
- Allows explicit override via configuration

**Implementation**:

```python
# src/services/search_factory.py
from src.storage.providers.factory import get_provider

def get_bm25_strategy(session: Session) -> BM25SearchStrategy:
    """
    Get the best available BM25 strategy for current database backend.

    Selection order:
    1. Explicit override via SEARCH_BM25_STRATEGY env var
    2. pg_search if available (Supabase, local with extension)
    3. PostgreSQL native FTS (fallback, works everywhere)
    """
    # Check for explicit override
    override = settings.search_bm25_strategy
    if override == "paradedb":
        return ParadeDBBM25Strategy(session)
    elif override == "native":
        return PostgresNativeFTSStrategy(session)

    # Auto-detect based on extension availability
    if _check_pg_search_available(session):
        return ParadeDBBM25Strategy(session)

    return PostgresNativeFTSStrategy(session)


def _check_pg_search_available(session: Session) -> bool:
    """Check if pg_search extension is installed and usable."""
    try:
        result = session.execute(text(
            "SELECT 1 FROM pg_extension WHERE extname = 'pg_search'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False
```

**Configuration**:
```bash
# .env - Optional explicit override
SEARCH_BM25_STRATEGY=native  # Force native FTS even if pg_search available
```

### Decision 3: Pluggable Embedding Provider Protocol

**What**: Define an `EmbeddingProvider` protocol with implementations for OpenAI, Voyage AI, Cohere, and local sentence-transformers.

**Why**:
- Different providers optimize for different use cases (cost, quality, privacy)
- Voyage AI specifically optimizes for RAG/retrieval scenarios
- Local models enable air-gapped deployments
- Provider switching should not require code changes

**Implementation**:

```python
# src/services/embedding.py
from typing import Protocol
from abc import abstractmethod

class EmbeddingProvider(Protocol):
    """Protocol for embedding generation providers."""

    @property
    def name(self) -> str:
        """Provider identifier."""
        ...

    @property
    def dimensions(self) -> int:
        """Output vector dimensions."""
        ...

    @property
    def max_tokens(self) -> int:
        """Maximum input tokens per text."""
        ...

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts (batched for efficiency)."""
        ...


class OpenAIEmbeddingProvider:
    """OpenAI text-embedding-3-small/large."""

    MODELS = {
        "text-embedding-3-small": {"dimensions": 1536, "max_tokens": 8191},
        "text-embedding-3-large": {"dimensions": 3072, "max_tokens": 8191},
        "text-embedding-ada-002": {"dimensions": 1536, "max_tokens": 8191},
    }

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._config = self.MODELS[model]

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

    @property
    def dimensions(self) -> int:
        return self._config["dimensions"]

    @property
    def max_tokens(self) -> int:
        return self._config["max_tokens"]

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]


class VoyageEmbeddingProvider:
    """Voyage AI embeddings optimized for retrieval."""

    MODELS = {
        "voyage-3": {"dimensions": 1024, "max_tokens": 32000},
        "voyage-3-lite": {"dimensions": 512, "max_tokens": 32000},
        "voyage-code-3": {"dimensions": 1024, "max_tokens": 32000},
    }

    def __init__(self, model: str = "voyage-3"):
        self.model = model
        self._client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        self._config = self.MODELS[model]

    @property
    def name(self) -> str:
        return f"voyage/{self.model}"

    @property
    def dimensions(self) -> int:
        return self._config["dimensions"]

    async def embed(self, text: str) -> list[float]:
        result = await self._client.embed([text], model=self.model)
        return result.embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        result = await self._client.embed(texts, model=self.model)
        return result.embeddings


class CohereEmbeddingProvider:
    """Cohere embed-english-v3.0 with input_type optimization."""

    MODELS = {
        "embed-english-v3.0": {"dimensions": 1024, "max_tokens": 512},
        "embed-english-light-v3.0": {"dimensions": 384, "max_tokens": 512},
        "embed-multilingual-v3.0": {"dimensions": 1024, "max_tokens": 512},
    }

    def __init__(self, model: str = "embed-english-v3.0"):
        self.model = model
        self._client = cohere.AsyncClient(api_key=settings.cohere_api_key)
        self._config = self.MODELS[model]

    @property
    def name(self) -> str:
        return f"cohere/{self.model}"

    @property
    def dimensions(self) -> int:
        return self._config["dimensions"]

    async def embed(self, text: str) -> list[float]:
        # Use "search_document" for indexing, "search_query" for queries
        response = await self._client.embed(
            texts=[text],
            model=self.model,
            input_type="search_document",
        )
        return response.embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embed(
            texts=texts,
            model=self.model,
            input_type="search_document",
        )
        return response.embeddings


class LocalEmbeddingProvider:
    """Local sentence-transformers models (no API calls)."""

    MODELS = {
        "all-MiniLM-L6-v2": {"dimensions": 384, "max_tokens": 256},
        "all-mpnet-base-v2": {"dimensions": 768, "max_tokens": 384},
        "multi-qa-MiniLM-L6-cos-v1": {"dimensions": 384, "max_tokens": 512},
    }

    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = model
        self._encoder = SentenceTransformer(model)
        self._config = self.MODELS.get(model, {"dimensions": 384, "max_tokens": 256})

    @property
    def name(self) -> str:
        return f"local/{self.model}"

    @property
    def dimensions(self) -> int:
        return self._config["dimensions"]

    async def embed(self, text: str) -> list[float]:
        # sentence-transformers is sync, run in thread pool
        embedding = await asyncio.to_thread(
            lambda: self._encoder.encode(text, convert_to_numpy=True).tolist()
        )
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = await asyncio.to_thread(
            lambda: self._encoder.encode(texts, convert_to_numpy=True).tolist()
        )
        return embeddings
```

### Decision 4: Embedding Provider Factory

**What**: Factory function to create the appropriate embedding provider based on configuration.

**Implementation**:

```python
# src/services/embedding.py

def get_embedding_provider() -> EmbeddingProvider:
    """
    Get embedding provider based on configuration.

    Environment variables:
    - EMBEDDING_PROVIDER: openai | voyage | cohere | local
    - EMBEDDING_MODEL: Model name within provider (optional, uses default)
    """
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

**Configuration**:
```bash
# .env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
# Or for local:
# EMBEDDING_PROVIDER=local
# EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Decision 5: Variable Dimension Vector Column

**What**: Store embedding dimensions in settings and use them when creating the pgvector column.

**Why**:
- Different providers have different dimensions
- Allows switching providers without schema changes (if dimensions match)
- Migration creates column with configured dimensions

**Implementation**:

```python
# src/config/settings.py
class Settings(BaseSettings):
    # Embedding configuration
    embedding_provider: str = "openai"
    embedding_model: str | None = None
    embedding_dimensions: int = 1536  # Default for OpenAI text-embedding-3-small

    # Search configuration
    search_bm25_strategy: str | None = None  # Auto-detect if not set
```

```python
# alembic/versions/xxx_add_hybrid_search.py
from src.config.settings import settings

def upgrade():
    dimensions = settings.embedding_dimensions

    op.add_column(
        'document_chunks',
        sa.Column('embedding', Vector(dimensions), nullable=True)
    )
```

**Trade-off**: Changing embedding provider with different dimensions requires re-creating the column and re-indexing all content.

### Decision 6: Hybrid Search Service with Injected Strategies

**What**: Modify `HybridSearchService` to accept both BM25 strategy and embedding provider as dependencies.

**Implementation**:

```python
# src/services/search.py

class HybridSearchService:
    """Combines BM25 and vector search with Reciprocal Rank Fusion."""

    RRF_K = 60  # Standard RRF constant

    def __init__(
        self,
        session: Session,
        bm25_strategy: BM25SearchStrategy | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.session = session
        self.bm25_strategy = bm25_strategy or get_bm25_strategy(session)
        self.embedding_provider = embedding_provider or get_embedding_provider()

    async def search(
        self,
        query: str,
        source_types: list[str] | None = None,
        limit: int = 20,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
    ) -> list[SearchResult]:
        """
        Perform hybrid search with Reciprocal Rank Fusion.

        Args:
            query: Search query string
            source_types: Filter by "content", "summary", "digest"
            limit: Maximum results to return
            bm25_weight: Weight for BM25 results in RRF (0-1)
            vector_weight: Weight for vector results in RRF (0-1)

        Returns:
            List of SearchResult with RRF scores and rank info
        """
        search_limit = limit * 5  # Get more for fusion

        # Run BM25 and vector search in parallel
        bm25_results, vector_results = await asyncio.gather(
            self.bm25_strategy.search(query, search_limit, source_types),
            self._vector_search(query, search_limit, source_types),
        )

        # Build rank maps
        bm25_ranks = {chunk_id: rank for chunk_id, rank in bm25_results}
        vector_ranks = {chunk_id: rank for chunk_id, rank in vector_results}

        # Calculate RRF scores
        all_chunk_ids = set(bm25_ranks.keys()) | set(vector_ranks.keys())
        rrf_scores: dict[int, float] = {}

        for chunk_id in all_chunk_ids:
            score = 0.0
            if chunk_id in bm25_ranks:
                score += bm25_weight / (self.RRF_K + bm25_ranks[chunk_id])
            if chunk_id in vector_ranks:
                score += vector_weight / (self.RRF_K + vector_ranks[chunk_id])
            rrf_scores[chunk_id] = score

        # Sort and fetch details
        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda x: rrf_scores[x],
            reverse=True
        )[:limit]

        return await self._build_results(
            sorted_ids, rrf_scores, bm25_ranks, vector_ranks
        )

    async def _vector_search(
        self,
        query: str,
        limit: int,
        source_types: list[str] | None,
    ) -> list[tuple[int, int]]:
        """Semantic search using configured embedding provider."""
        query_embedding = await self.embedding_provider.embed(query)

        stmt = text("""
            SELECT id, embedding <=> :embedding as distance
            FROM document_chunks
            WHERE embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT :limit
        """)

        result = self.session.execute(stmt, {
            "embedding": str(query_embedding),
            "limit": limit
        })

        return [(row.id, idx + 1) for idx, row in enumerate(result.fetchall())]
```

### Decision 7: Native FTS Schema Requirements

**What**: Add TSVECTOR column with automatic trigger updates and GIN index.

**Implementation** (migration):

```python
# alembic/versions/xxx_add_hybrid_search.py

def upgrade():
    # Add search_vector column for native FTS
    op.add_column(
        'document_chunks',
        sa.Column('search_vector', TSVECTOR, nullable=True)
    )

    # Create GIN index for fast FTS queries
    op.execute("""
        CREATE INDEX ix_document_chunks_search_vector
        ON document_chunks USING gin (search_vector)
    """)

    # Create trigger to auto-update search_vector
    op.execute("""
        CREATE OR REPLACE FUNCTION document_chunks_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.chunk_text, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER document_chunks_search_vector_trigger
        BEFORE INSERT OR UPDATE OF chunk_text ON document_chunks
        FOR EACH ROW EXECUTE FUNCTION document_chunks_search_vector_update();
    """)

    # Backfill existing chunks
    op.execute("""
        UPDATE document_chunks
        SET search_vector = to_tsvector('english', COALESCE(chunk_text, ''))
        WHERE search_vector IS NULL
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS document_chunks_search_vector_trigger ON document_chunks")
    op.execute("DROP FUNCTION IF EXISTS document_chunks_search_vector_update()")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector")
    op.drop_column('document_chunks', 'search_vector')
```

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Native FTS quality < BM25 | Lower search relevance on Neon | Document quality difference, recommend pg_search for production |
| Embedding dimension mismatch | Can't switch providers freely | Standardize on 1536 (OpenAI), or plan for re-indexing |
| Local model memory usage | High RAM for sentence-transformers | Document requirements, recommend cloud providers for limited resources |
| Strategy detection overhead | Slight startup latency | Cache detection result per session |
| Cohere input_type mismatch | Query vs document embedding difference | Use `search_query` type for query embedding |

## Migration Plan

1. **Phase 1**: Add schema changes
   - Add `search_vector` TSVECTOR column
   - Create trigger and GIN index
   - Backfill existing chunks (if any)

2. **Phase 2**: Implement provider abstractions
   - BM25SearchStrategy protocol and implementations
   - EmbeddingProvider protocol and implementations
   - Factory functions with auto-detection

3. **Phase 3**: Update HybridSearchService
   - Inject strategies via constructor
   - Update search endpoint to use factories

4. **Phase 4**: Documentation
   - Document backend compatibility matrix
   - Add embedding provider comparison (cost, quality, speed)
   - Update deployment guides per backend

## Open Questions

1. Should we support query-time embedding provider override (e.g., for A/B testing)?
2. Should we add embedding caching to reduce API costs for repeated queries?
3. For Cohere, should we always use `search_query` input_type for query embeddings?
4. Should we expose BM25 strategy name in search response metadata?
