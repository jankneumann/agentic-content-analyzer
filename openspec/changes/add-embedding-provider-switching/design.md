## Context

The embedding infrastructure (`src/services/embedding.py`) has a clean `EmbeddingProvider` Protocol with 4 implementations and a factory function. However, the database schema (`document_chunks.embedding vector(384)`) and ORM model are locked to 384 dimensions. Changing to a production-grade provider (OpenAI 1536, Voyage 1024) requires manual ALTER TABLE + index rebuild. There is no tooling to orchestrate this safely, no metadata tracking which provider generated each embedding, and no validation that config matches database state.

The local provider (`LocalEmbeddingProvider`) hardcodes 3 sentence-transformers models in a `_dimensions_map` and cannot support modern instruction-tuned models (like `gte-Qwen2-1.5B-instruct`) that need `trust_remote_code=True` and asymmetric query/document prompts.

Additionally, providers with asymmetric embedding (Cohere: `search_query` vs `search_document`; Voyage: `query` vs `document`; instruction-tuned local models: `prompt_name="query"`) are currently hardcoded to document mode even when embedding search queries — a latent quality bug.

## Goals / Non-Goals

- Goals:
  - Enable safe, one-command switching between embedding providers
  - Support arbitrary sentence-transformers models including instruction-tuned ones
  - Fix query/document asymmetry across all providers to improve retrieval quality
  - Track embedding provenance (which provider/model generated each vector)
  - Detect config-vs-DB mismatches at startup
  - Maintain backward compatibility with existing BM25-only search

- Non-Goals:
  - Multi-provider columns (storing embeddings from multiple providers simultaneously)
  - Cross-provider score normalization or RRF merging across providers
  - Automatic provider selection based on content type
  - Matryoshka / dimensionality reduction support

## Decisions

- **Decision**: Use unconstrained `Vector()` in the ORM model instead of `Vector(384)`.
  - Rationale: `Vector(N)` is evaluated at Python class-definition time and cannot be made dynamic from Settings. pgvector supports unconstrained `Vector()` and HNSW indexes still work. Dimension enforcement moves to the application layer via Settings validation.
  - Alternatives considered: (1) Dynamic metaclass tricks to read Settings at import time — rejected, fragile and non-standard. (2) Remove ORM mapping entirely (raw SQL only like `search_vector`) — rejected, loses pgvector's `cosine_distance()` operator support.

- **Decision**: Use runtime `ALTER TABLE` for provider switching, not Alembic migrations.
  - Rationale: Switching providers is an operational action, not schema evolution. Different environments (dev=384, staging=1536) already have different dimensions. Alembic migrations are version-controlled and applied once; provider switching may happen multiple times. The one-time migration only adds metadata columns and unconstrains the vector.
  - Alternatives considered: Generate per-switch Alembic migrations — rejected, clutters migration history with operational actions.

- **Decision**: Add `is_query: bool = False` parameter to existing `embed()`/`embed_batch()` methods rather than separate `embed_query()`/`embed_documents()` methods.
  - Rationale: Backward-compatible (all existing callers get `is_query=False` default). Only one call site (`search.py` line 181) needs `is_query=True`. Avoids protocol surface area expansion.
  - Alternatives considered: Separate methods — rejected, doubles protocol surface and requires updating all callers to use the "documents" variant.

- **Decision**: Auto-detect dimensions from loaded model via `model.get_sentence_embedding_dimension()` with fallback to known-model map.
  - Rationale: The `dimensions` property is called before the model is lazy-loaded (e.g., in settings validation). Known models get the right answer without loading; unknown models use `settings.embedding_dimensions` as fallback, then self-correct once loaded.

- **Decision**: Tag existing embeddings as `embedding_provider='unknown'` in the migration.
  - Rationale: Existing data predates metadata tracking. The switch command NULLs all embeddings anyway, so the "unknown" tag is a safety marker, not a permanent state.

## Risks / Trade-offs

- Risk: Unconstrained `Vector()` allows mixed-dimension vectors in the same column.
  - Mitigation: Application-layer validation. Startup mismatch check warns if embeddings don't match config. Switch command NULLs all embeddings before re-embedding.

- Risk: `trust_remote_code=True` for sentence-transformers models is a security concern.
  - Mitigation: Setting defaults to `false`. User must explicitly opt in via `EMBEDDING_TRUST_REMOTE_CODE=true`. Only affects local model loading, not API providers.

- Risk: Switch command clears all embeddings, making vector search unavailable during backfill.
  - Mitigation: BM25 search continues to work. The `--skip-backfill` flag allows clearing without immediately re-embedding (e.g., for scheduled overnight backfill). Progress reporting during backfill.

- Risk: Startup mismatch check adds a DB query on every API startup.
  - Mitigation: Wrapped in try/except, non-blocking, warn-only. Single lightweight query with DISTINCT on two columns.

## Migration Plan

1. Run Alembic migration: adds metadata columns, unconstrains vector column, tags existing embeddings as 'unknown'
2. Deploy code changes (protocol fix, enhanced local provider, metadata writes)
3. All new embeddings automatically get correct metadata
4. Run `aca manage switch-embeddings` to migrate to desired provider (if switching)

## Open Questions

None — all design decisions resolved during planning.
