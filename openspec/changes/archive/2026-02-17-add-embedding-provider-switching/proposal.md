# Change: Add Embedding Provider Switching & Enhanced Local Provider

## Why

The document search system has 4 embedding providers implemented (OpenAI, Voyage, Cohere, Local) with a clean Protocol-based abstraction, but the vector column is hardcoded to `vector(384)` — matching only the default local model. Switching providers requires manual DB surgery (ALTER TABLE, NULL embeddings, rebuild index). Additionally, the `LocalEmbeddingProvider` only supports 3 hardcoded models and cannot handle modern instruction-tuned models like `gte-Qwen2-1.5B-instruct` (1536 dims, asymmetric query/document encoding, `trust_remote_code=True`). There is also a latent bug: Cohere and Voyage always use "document" input types even when embedding search queries, degrading retrieval quality for asymmetric models.

## What Changes

- Fix query/document asymmetry across all embedding providers (Cohere `search_query`, Voyage `query`, Local `prompt_name="query"`)
- Enhance `LocalEmbeddingProvider` to support arbitrary sentence-transformers models, including instruction-tuned models with custom prompts
- Add `embedding_provider` and `embedding_model` metadata columns to `document_chunks` for provenance tracking
- Unconstrain the vector column from `vector(384)` to `vector()` so any provider's dimensions work
- Add `aca manage switch-embeddings` CLI command to safely orchestrate provider changes
- Add startup mismatch detection (warn if DB embeddings don't match current config)
- Add `embedding_trust_remote_code` and `embedding_max_seq_length` settings

## Impact

- Affected specs: `document-search`, `cli-interface`
- Affected code:
  - `src/services/embedding.py` (protocol, all 4 providers, mismatch check)
  - `src/models/chunk.py` (ORM columns)
  - `src/services/search.py` (query embedding call)
  - `src/services/indexing.py` (metadata writes)
  - `src/scripts/backfill_chunks.py` (metadata writes)
  - `src/config/settings.py` (new settings, validation)
  - `src/cli/manage_commands.py` (new CLI command)
  - `src/scripts/switch_embeddings.py` (new orchestration module)
  - `alembic/versions/` (new migration)
  - `profiles/base.yaml` (new settings)
  - `tests/` (new and updated tests)
- Breaking changes: None — unconstrained `Vector()` is backward-compatible with existing `vector(384)` data
