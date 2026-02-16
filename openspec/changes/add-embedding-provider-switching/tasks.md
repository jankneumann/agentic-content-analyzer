# Tasks: Add Embedding Provider Switching & Enhanced Local Provider

## 1. Database Schema

- [x] 1.1 Create Alembic migration to add `embedding_provider` (VARCHAR 50) and `embedding_model` (VARCHAR 100) columns to `document_chunks` (down_revision: `f9a8b7c6d5e5`)
- [x] 1.2 In same migration: ALTER embedding column from `vector(384)` to unconstrained `vector` via `ALTER COLUMN embedding TYPE vector USING embedding::vector`
- [x] 1.3 In same migration: create composite index `ix_document_chunks_embedding_meta` on `(embedding_provider, embedding_model)`
- [x] 1.4 In same migration: backfill existing rows with `embedding_provider='unknown', embedding_model='unknown'` where embedding IS NOT NULL

## 2. ORM Model Update

- [x] 2.1 Update `DocumentChunk` — embedding column is not ORM-mapped (stays raw SQL), noted as unconstrained `vector` in docstring
- [x] 2.2 Add `embedding_provider = Column(String(50), nullable=True)` and `embedding_model = Column(String(100), nullable=True)` columns to `DocumentChunk`
- [x] 2.3 Update docstring to note dimension is provider-determined, not fixed

## 3. Fix Query/Document Asymmetry

- [x] 3.1 Add `is_query: bool = False` keyword parameter to `EmbeddingProvider` protocol's `embed()` and `embed_batch()` methods in `src/services/embedding.py`
- [x] 3.2 Update `OpenAIEmbeddingProvider` to accept and ignore `is_query` (symmetric model)
- [x] 3.3 Fix `VoyageEmbeddingProvider` to use `input_type="query"` when `is_query=True`, `"document"` otherwise
- [x] 3.4 Fix `CohereEmbeddingProvider` to use `input_type="search_query"` when `is_query=True`, `"search_document"` otherwise; removed `self._input_type` instance var
- [x] 3.5 Update `HybridSearchService._vector_search()` in `src/services/search.py` to pass `is_query=True` to `self._embedder.embed(query, is_query=True)`

## 4. Enhanced Local Embedding Provider

- [x] 4.1 Refactor `LocalEmbeddingProvider._get_model()` to pass `trust_remote_code=settings.embedding_trust_remote_code` to `SentenceTransformer()`
- [x] 4.2 Auto-detect dimensions after model load via `model.get_sentence_embedding_dimension()`; store in `self._detected_dimensions`
- [x] 4.3 Auto-detect query prompt support via `getattr(model, 'prompts', {}).get('query')`; store in `self._supports_query_prompt`
- [x] 4.4 Override `model.max_seq_length` if `settings.embedding_max_seq_length` is set
- [x] 4.5 Update `embed_batch()` to use `prompt_name="query"` when `is_query=True` and model supports query prompts
- [x] 4.6 Update `dimensions` property to use `_detected_dimensions` when available, fall back to known-model map, then `settings.embedding_dimensions`
- [x] 4.7 Update `max_tokens` property to use `model.max_seq_length` when model is loaded

## 5. Metadata Tracking

- [x] 5.1 Update `_index_content_impl()` in `src/services/indexing.py` to write `embedding_provider` and `embedding_model` via raw SQL UPDATE (also fixed `CAST(:embedding AS vector)` bug)
- [x] 5.2 Update `_backfill_full()` in `src/scripts/backfill_chunks.py` to write metadata after embedding assignment
- [x] 5.3 Update `_backfill_embeddings_only()` in `src/scripts/backfill_chunks.py` to include metadata in UPDATE

## 6. Settings & Validation

- [x] 6.1 Add `embedding_trust_remote_code: bool = False` and `embedding_max_seq_length: int | None = None` to Settings
- [x] 6.2 Enhance `validate_search_config()` to warn if `embedding_dimensions` doesn't match known provider/model dimensions
- [x] 6.3 Add settings to `profiles/base.yaml` under `settings.search`

## 7. Startup Mismatch Detection

- [x] 7.1 Add `check_embedding_config_mismatch(db: Session) -> dict | None` in new `src/services/embedding_check.py`
- [x] 7.2 Integrate mismatch check into API startup in `src/api/app.py` lifespan (warn-only, non-blocking, try/except wrapped)

## 8. Switch Embeddings CLI Command

- [x] 8.1 Create `src/scripts/switch_embeddings.py` with async function
- [x] 8.2 Add `switch-embeddings` command to `src/cli/manage_commands.py` with all options
- [x] 8.3 Add confirmation prompt before destructive action (unless `--yes`)

## 9. Tests

- [x] 9.1 Create `tests/services/test_embedding_providers.py` with tests for `is_query` parameter across all 4 providers
- [x] 9.2 Add tests for `LocalEmbeddingProvider` auto-dimension detection and query prompt support
- [x] 9.3 Create `tests/scripts/test_switch_embeddings.py` with dry-run, clear embeddings, and error tests
- [x] 9.4 Update `tests/api/test_search_api.py` `_search_columns` fixture: change `vector(384)` to `vector`
- [x] 9.5 Update `seeded_content` fixture to include `embedding_provider` and `embedding_model` values

## 10. Documentation

- [x] 10.1 Add "Switching Embedding Providers" section to `docs/SEARCH.md` with command reference, duration estimates, advanced local models
- [x] 10.2 Update CLAUDE.md Critical Gotchas with embedding-related gotchas and new CLI commands
