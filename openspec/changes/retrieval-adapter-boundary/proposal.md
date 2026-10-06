# Change: retrieval-adapter-boundary

## Why

Retrieval is implemented twice, both times welded to Postgres. `HybridSearchService`
(`src/services/search.py`) fuses a BM25 leg and a pgvector leg over `document_chunks`;
`MemoryProvider` (`src/agents/memory/provider.py`) fuses graph, vector, and keyword
strategies over `agent_memories` with its own copy of weighted RRF and a circuit
breaker. Every embedding write is raw SQL spread across `indexing.py`,
`backfill_chunks.py`, and `switch_embeddings.py` because the vector column is unmapped.
BM25 quality depends on which host happens to have `pg_search`, and the only way to
evaluate an alternative engine is to fork the service.

Object-storage-native engines (LanceDB, Infino, turbopuffer) now offer hybrid search
over Parquet-class files with pushdown filters and near-zero idle cost. Adopting one
is not justified at today's corpus size, but *being unable to try one without a fork*
is the actual problem. The evaluation that preceded this proposal ranked LanceDB as
the second adapter to build, Infino as a watch-list item until 1.0, and turbopuffer as
a hosted option only. A provider-adapter boundary with an evaluation harness turns
that judgement into something measurable and repeatable.

## What Changes

- Introduce a `RetrievalAdapter` protocol in `src/retrieval/` with four actions and a
  health probe: `write` (upsert chunks or memories with embeddings), `search`
  (BM25, vector, or hybrid candidates with typed filters), `read` (fetch records by id),
  `improve` (index maintenance: optimize, compact, fold new rows into the text index,
  rebuild after an embedding switch), and `health_check`.
- Two namespaces share the protocol: `content_chunks` and `agent_memories`. Each
  namespace has a typed record model and a typed filter model; adapters translate
  filters, they never receive SQL fragments.
- A `PostgresRetrievalAdapter` absorbs `ParadeDBBM25Strategy`,
  `PostgresNativeFTSStrategy`, the pgvector similarity query, the raw-SQL embedding
  writes from `indexing.py` and the two scripts, and the `agent_memories` vector and
  keyword strategies. Behavior is byte-for-byte identical: same SQL, same strategy
  names in `SearchMeta.bm25_strategy`, same ranked ids on the fixture corpus.
- Fusion (weighted RRF), reranking, LLM tree search, document aggregation, highlight
  generation, and the memory circuit breaker stay **above** the adapter in a
  `RetrievalService`; adapters return per-leg candidate lists only.
- A `LanceDBRetrievalAdapter` behind `RETRIEVAL_SECONDARY_ADAPTER=lancedb` (default
  unset) writes to a local path or an S3-compatible URI using the provider-neutral
  `backup_s3_*` credential pattern. Dual-write is fail-safe: a secondary write failure
  is logged and never fails ingestion, backfill, or the embedding switch.
- Shadow-read mode (`RETRIEVAL_SHADOW_READ=true`) runs the secondary adapter after the
  primary response is built, off the request path, and records overlap, rank
  correlation, and latency without changing the response.
- The `improve` action is wired to `aca manage backfill-chunks`,
  `aca manage switch-embeddings`, and a new `aca manage optimize-index` command.
- `aca evaluate` gains a `retrieval` dataset kind (query plus relevant content ids) and
  a `retrieval-compare` command reporting recall@k, MRR, and p50/p95 latency per
  adapter, persisted in the existing `evaluation_datasets` and `evaluation_results`
  tables.
- `SearchMeta` gains `retrieval_adapter` and optional `shadow` fields. Existing fields
  and values are unchanged.
- Infino and turbopuffer are documented as future adapters in `docs/SEARCH.md` with the
  protocol methods each would need and the known gaps (single writer, hosted-only).
- **BREAKING** for internal imports only: `get_bm25_strategy` and the two strategy
  classes move under `src/retrieval/adapters/postgres/`; `search_strategy.py` keeps
  re-export shims for one release.

## Non-Functional Requirements

| Attribute | Metric | Target | Verified by (phase) |
|-----------|--------|--------|---------------------|
| Compatibility | Ranked content ids and `SearchMeta.bm25_strategy` for the search regression fixture, adapter extracted vs. baseline | Identical ordering, identical strategy names | Golden test in `tests/retrieval/test_postgres_parity.py`, CI |
| Performance | p95 of `SearchMeta.query_time_ms` on the regression fixture, Postgres adapter vs. baseline | Regression ≤ 10 % | Performance check in `tests/regression/test_search_latency.py`, CI |
| Performance | Added request-path latency when shadow read is enabled | 0 ms on the response; shadow work runs after the response is built | Unit test asserts response is returned before shadow task starts |
| Resilience | Ingestion, backfill, and switch-embeddings outcome when the secondary adapter raises | Primary write commits; failure logged with adapter name; no exception propagates | `tests/retrieval/test_dual_write.py` |
| Resilience | Memory recall when one adapter leg fails | Behavior per `agentic-analysis` scenario 26 unchanged (skip, redistribute weights, 60 s cooldown) | Existing `tests/agents/memory/test_provider.py` stays green unmodified |
| Observability | Every adapter call emits `retrieval.<namespace>.<action>` with adapter name and duration | 100 % of actions instrumented | Log-capture test per action |
| Operability | LanceDB adapter with no configuration | Adapter reports unavailable; primary path unaffected; startup logs one line | `tests/retrieval/test_lancedb_adapter.py` |
| Compatibility | `get_embedding_provider`, `embed_chunks`, `EmbeddingProvider`, `RerankProvider` signatures | Unchanged (≈ 30 dependents each) | `mypy` plus import-shim tests |

## Approaches Considered

### Approach 1: Protocol extraction with a composition layer

Description: Define `RetrievalAdapter` per namespace, move all Postgres SQL into one
adapter, and place a `RetrievalService` above it that owns fusion, reranking, tree
search, aggregation, and the memory circuit breaker. `HybridSearchService` and
`MemoryProvider` become thin consumers. LanceDB implements the same protocol.

Pros:
- Adapters stay small: one write, one search per leg, one read, one improve.
- Fusion logic exists once instead of twice; the memory RRF constants and the search RRF
  constants become one configurable policy.
- Filter pushdown is a first-class adapter concern, so LanceDB and Infino can express
  filters natively instead of receiving a content-id list.
- Dual-write and shadow-read are properties of the service, not of each adapter.

Cons:
- Largest diff: touches `search.py`, `search_strategy.py`, `indexing.py`, both
  scripts, and `src/agents/memory/`.
- Requires the memory spec's RRF behavior to be re-proved by existing tests after the
  refactor.

Effort: L, split into three M packages (extract, LanceDB, evaluation).

### Approach 2: Per-leg strategy generalization

Description: Keep `HybridSearchService` and `MemoryProvider` as they are and extend the
existing `BM25SearchStrategy` pattern with a `VectorSearchStrategy` and a
`ChunkWriteStrategy`. LanceDB implements each leg as a separate strategy selected by
settings.

Pros:
- Smallest diff; follows a pattern already in `search_strategy.py`.
- No change to the memory stack.

Cons:
- LanceDB and Infino run hybrid search as one query with native filters; splitting them
  into two legs plus an external content-id pre-filter discards the main reason to
  evaluate them.
- Fusion remains duplicated between search and memory.
- Write path stays raw SQL in three places; dual-write must be added to each.

Effort: M.

### Approach 3: Whole-service adapter

Description: Abstract at the `search(SearchQuery) -> SearchResponse` level. Each backend
implements the entire pipeline including fusion, reranking, and aggregation.

Pros:
- Simplest interface: one method, one response model.
- Backends can use engine-native fusion.

Cons:
- Reranking, tree search, highlighting, and document aggregation get reimplemented per
  backend or fall out of parity.
- Agent memory cannot share it; the memory stack stays separate.
- Shadow comparison compares whole responses, so a ranking difference cannot be
  attributed to a leg.

Effort: M.

### Recommended

Approach 1. It is the only option that gives the second adapter native hybrid search
with pushdown filters, which is the property the evaluation is meant to measure. It
also removes the duplicated RRF implementation, which Approach 2 keeps and Approach 3
multiplies. The size is mitigated by the package split and by the parity golden test,
which pins behavior before any adapter is swapped.

### Selected Approach

Approach 1, selected at Gate 1 with no modifications. Discovery answers that shape it:
both namespaces (`content_chunks`, `agent_memories`) are unified now; the full write
path (index hook, backfill, switch-embeddings) routes through the adapter; `improve`
means index maintenance only in this version; the evaluation harness extends
`aca evaluate` rather than adding a separate command group.

Approaches 2 and 3 were rejected: Approach 2 cannot exercise single-query hybrid
search with native filters, which is the property under evaluation, and Approach 3
multiplies reranking and tree search per backend while excluding agent memory.

## Capabilities

### New Capabilities
- `retrieval-adapter`: the adapter protocol, namespaces, typed filters, adapter
  registry and settings, Postgres parity, LanceDB adapter, dual-write, shadow-read,
  and the improve action.
- `retrieval-evaluation`: retrieval dataset kind, recall@k / MRR / latency metrics,
  `aca evaluate retrieval-compare`, and result persistence.

### Modified Capabilities
- `document-search`: the Search Response Metadata requirement gains
  `retrieval_adapter` and optional `shadow` fields; the Cross-Backend Compatibility
  requirement names the adapter as the selection point rather than the BM25 strategy
  factory.

## Impact

- Code: `src/services/search.py`, `src/services/search_strategy.py` (shim),
  `src/services/indexing.py`, `src/scripts/backfill_chunks.py`,
  `src/scripts/switch_embeddings.py`, `src/agents/memory/provider.py` and
  `strategies/{vector,keyword}.py`, `src/models/search.py`, `src/config/settings.py`,
  `src/cli/manage_commands.py`, `src/cli/evaluate_commands.py`,
  `src/services/evaluation_service.py`, `src/models/evaluation.py`; new package
  `src/retrieval/`.
- Dependencies: `lancedb` and `pyarrow` as an optional extra `[lancedb]`, never
  imported at module load.
- Data: one Alembic migration adding `dataset_kind` to `evaluation_datasets` and a
  nullable JSON `relevant_ids` on `evaluation_samples`. No change to
  `document_chunks` or `agent_memories`.
- Specs: `openspec/specs/document-search` delta; new `retrieval-adapter` and
  `retrieval-evaluation` specs.
- Coordination: `verify-production-paradedb-langfuse` relies on
  `meta.bm25_strategy=paradedb_bm25`; preserved. `operationalize-llm-evaluation-routing`
  owns `evaluation_service.py`; the retrieval additions are confined to a new module
  `src/evaluation/retrieval_metrics.py` plus one new service method.
- Docs: `docs/SEARCH.md`, `docs/ACA-AGENTS.md`, `docs/GOTCHAS.md`, `CLAUDE.md` command
  list, and an ADR under `docs/decisions/`.
