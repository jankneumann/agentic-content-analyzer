# Design: retrieval-adapter-boundary

## Context

Two retrieval stacks exist today. `src/services/search.py` runs BM25 (via the
strategy protocol in `search_strategy.py`) and pgvector over `document_chunks`, then
fuses with weighted RRF, optionally reranks, runs LLM tree search, aggregates to
documents, and highlights. `src/agents/memory/provider.py` runs graph, vector, and
keyword strategies over `agent_memories`, fuses with its own RRF, and guards each
strategy with a circuit breaker. Both are Postgres-only. Every embedding write is raw
SQL because the vector column is unmapped, and it lives in three places:
`indexing.py`, `backfill_chunks.py`, and `switch_embeddings.py`.

Consumers already receive the search service by injection: `search_routes.py`,
`mcp_tools/content.py`, and the research specialist. `EmbeddingProvider` and
`RerankProvider` are protocols with cached factories and roughly thirty dependents
each; they are not changing. `FileStorageProvider` and the provider-neutral
`backup_s3_*` settings block are the object-storage precedents.

Constraints from adjacent work: `verify-production-paradedb-langfuse` treats
`meta.bm25_strategy=paradedb_bm25` as production evidence, and
`operationalize-llm-evaluation-routing` owns `evaluation_service.py`. Neither has
started.

## Goals / Non-Goals

Goals:
- One adapter contract, two namespaces, one fusion implementation.
- Postgres behavior provably unchanged when no secondary adapter is configured.
- LanceDB usable as a secondary adapter with dual-write and shadow-read.
- Retrieval quality measurable per adapter through `aca evaluate`.
- Infino and turbopuffer documented as future adapters against the same contract.

Non-Goals:
- Replacing Postgres as the system of record. `document_chunks` and
  `agent_memories` rows are still inserted by the ORM and remain the source of
  chunk identifiers.
- Relevance feedback or learned boosting. `improve` is index maintenance only.
- Moving the graph memory strategy behind the adapter. Graphiti is not a retrieval
  store in this sense; it stays a `MemoryStrategy`.
- Tree search inside adapters. It stays in the composition layer.
- Any change to the embedding or reranking provider interfaces.

## Decisions

### D1: Package layout

New package `src/retrieval/`:

```
src/retrieval/
  __init__.py
  protocol.py        # RetrievalAdapter protocol, SupportsAccessTracking extension
  models.py          # Namespace, ChunkRecord, MemoryRecord, ChunkFilter, MemoryFilter,
                     # Candidate, LegResults, ImproveReport
  rrf.py             # weighted_rrf(): the single fusion implementation
  service.py         # RetrievalService: fusion, rerank, tree search, aggregation
  registry.py        # settings-driven adapter construction, lazy imports
  dual_write.py      # CompositeAdapter: primary + fail-safe secondary
  shadow.py          # shadow read scheduling and comparison persistence
  telemetry.py       # structured events and counters
  adapters/
    postgres/        # adapter.py, bm25.py, vector.py, filters.py, writes.py, memory.py
    lancedb/         # adapter.py, schema.py, filters.py
```

`src/services/search.py` keeps `HybridSearchService` as a facade with its current
constructor and `search()` signature. `src/services/search_strategy.py` becomes a
re-export shim for one release. `src/agents/memory/` keeps `MemoryProvider` and
`MemoryStrategy` as public API.

### D2: Adapters return per-leg candidates; fusion lives above

`search()` returns `LegResults` with one ordered `list[Candidate]` per leg
(`bm25`, `vector`). A `Candidate` is `(id, score, parent_id)`. Adapters never fuse,
rerank, or truncate below the requested limit. `RetrievalService` fuses with
`rrf.weighted_rrf`, which absorbs both `HybridSearchService._calculate_rrf_multi` and
`MemoryProvider._weighted_rrf`. The memory constants (`k=60`, min score `0.01`, weight
redistribution) become parameters with the memory defaults, so `agentic-analysis`
scenario 22 is satisfied by configuration rather than by a second implementation.

Rejected: engine-native fusion inside adapters. It would make shadow comparisons
unattributable to a leg and would let LanceDB's RRF and Postgres RRF drift.

### D3: Typed filters, translated per adapter

`ChunkFilter` and `MemoryFilter` are Pydantic models. The Postgres adapter translates
`ChunkFilter` into the same content-id pre-resolution query that
`_resolve_content_filter` runs today and passes the id list to both legs; this is
what keeps parity byte-for-byte. `ChunkFilter.content_ids` is an explicit allow-list
so the resolved list can also be passed in by a caller. The LanceDB adapter translates
the same model into a SQL `where` string with parameters escaped by the library. An
adapter that receives a field it cannot translate raises `UnsupportedFilterError`
naming the field; silent drops are forbidden by spec.

### D4: HybridSearchService becomes a facade

Public constructor and `search(SearchQuery) -> SearchResponse` are unchanged so the
API route, the MCP tool, and the research specialist need no edits. Internally it
builds a `RetrievalService` from the registry, converts `SearchQuery.filters` into
`ChunkFilter`, and delegates. `SearchMeta` gains `retrieval_adapter: str` and
`shadow: ShadowMeta | None`. `bm25_strategy` is populated from the Postgres adapter's
reported strategy name, so its values are unchanged.

### D5: Memory namespace and the access-count update

`VectorStrategy` and `KeywordStrategy` become thin wrappers that call the Postgres
adapter's `agent_memories` namespace and wrap candidates back into `MemoryEntry`.
`GraphStrategy` is unchanged. `MemoryProvider` keeps its circuit breaker and calls
`rrf.weighted_rrf`. The recall-time `access_count` and `last_accessed_at` update
required by `agentic-analysis` scenario 9 is exposed as an optional protocol
extension `SupportsAccessTracking.touch(namespace, ids)`; the Postgres adapter
implements it, LanceDB does not, and `MemoryProvider` calls it when present. This
keeps the four-action contract intact while honoring the pinned behavior.

Rejected: a fifth mandatory action. It would force every adapter to model access
statistics that only the memory namespace uses.

### D6: Write means index write; row insert stays in the ORM

`document_chunks` rows are inserted by `indexing.py` through the ORM because their
ids are database-assigned and referenced by `content_references`. The Postgres
adapter's `write(content_chunks, records)` therefore performs the embedding and
provenance `UPDATE` for records that already carry ids. The secondary adapter's
`write` upserts full records keyed by chunk id. `indexing.py`, `backfill_chunks.py`,
and `switch_embeddings.py` build `ChunkRecord`s from the ORM rows and call the
registry's primary adapter, which is the composite adapter when a secondary is
configured. No raw embedding SQL remains outside `adapters/postgres/writes.py`.

### D7: Replacement and deletion without a delete verb

`write` accepts `replace_parent: bool`. When true, the records for each parent id in
the batch replace every prior record for that parent; this is how `reindex_content`
and the embedding switch remove stale chunks. Orphaned records whose parent no longer
exists in the system of record are removed by `improve`'s reconciliation step. The
content-delete listener in `indexing.py` calls `write(..., replace_parent=True)` with
an empty batch for the parent, which the Postgres adapter treats as a no-op (cascade
already handled it) and the LanceDB adapter treats as a delete.

### D8: LanceDB table layout

One table per namespace per embedding provider and dimension, named
`<namespace>__<provider>__<dims>`, so an embedding switch creates a new table and
`improve` drops tables for retired providers. Schema: `id` (int64), `parent_id`
(int64), `text` (large_utf8), `embedding` (fixed-size float32 list), provenance
columns, and the filterable metadata columns from `ChunkRecord` or `MemoryRecord`.
Full-text index on `text` with `optimize()` invoked by `improve`. Vector index built
when the table exceeds a configurable row threshold; below it, brute force is faster.
Filters use pre-filtering so candidate limits are filled from matching rows.

### D9: Shadow read is post-response and persisted

`RetrievalService.search` returns its result, then, if shadow read is enabled and the
secondary adapter is available, schedules `shadow.run_comparison` as a background
task on the running loop. The comparison stores a row in
`retrieval_shadow_comparisons` (query hash, namespace, mode, primary and secondary
adapter names, top-k ids from each, overlap@10, Spearman rank correlation over the
union, both latencies). The API layer never awaits it. Failures increment a counter
and log.

### D10: Evaluation extension

`evaluation_datasets.dataset_kind` (default `routing`) and
`evaluation_samples.relevant_ids` (JSONB, nullable) plus `evaluation_samples.provisional`
(bool, default false) are added by migration. `strong_model` and `weak_model` are
made nullable for retrieval datasets. Metric rows are stored in `evaluation_results`
with `judge_type='metric'`, `judge_model=<adapter>:<mode>`, `preference='n/a'`, and
the metric dictionary in `critiques`, which avoids a new table and keeps
`generate_report` working. Metrics live in `src/evaluation/retrieval_metrics.py`
with no dependency on `evaluation_service.py`; the service gains one method,
`run_retrieval_comparison`, to limit overlap with the routing work.

### D11: Settings

```
retrieval_primary_adapter: Literal["postgres"] = "postgres"
retrieval_secondary_adapter: Literal["lancedb"] | None = None
retrieval_shadow_read: bool = False
retrieval_lancedb_uri: str | None = None            # local dir or s3://bucket/prefix
retrieval_object_store_endpoint: str | None = None
retrieval_object_store_region: str = "auto"
retrieval_object_store_access_key_id: SecretStr | None = None
retrieval_object_store_secret_access_key: SecretStr | None = None
retrieval_lancedb_vector_index_min_rows: int = 50_000
```

Every field defaults to off. A validator rejects `retrieval_shadow_read=True`
without a secondary adapter and rejects an unknown adapter name with the known list.

### D12: Optional dependency and lazy import

`lancedb` and `pyarrow` go in a `[lancedb]` extra. `registry.py` imports the adapter
module inside the factory function; a missing extra yields an unavailable adapter and
one startup warning. This mirrors how `[embeddings]` is handled.

### D13: Observability

`telemetry.py` wraps every adapter action in a context manager that emits one
structured log record `retrieval.action` with adapter, namespace, action, count, and
duration, and maintains in-process counters `retrieval.secondary_write_failures` and
`retrieval.shadow_failures`. Counters are surfaced through the existing operations
diagnostics response so they are readable without a metrics backend.

### Fitness Functions

| NFR (from proposal.md) | Verifying check | Status |
|------------------------|-----------------|--------|
| Compatibility: identical ranked ids and strategy names on the regression fixture | `pytest tests/retrieval/test_postgres_parity.py` against a baseline JSON recorded before extraction | new |
| Performance: p95 query time regression ≤ 10 % | `pytest tests/regression/test_search_latency.py` comparing against the recorded baseline; marked `regression` | new |
| Performance: 0 ms request-path cost of shadow read | `tests/retrieval/test_shadow.py::test_response_returned_before_shadow_starts` | new |
| Resilience: secondary failure never fails ingestion, backfill, or switch | `pytest tests/retrieval/test_dual_write.py` | new |
| Resilience: memory degradation unchanged | `pytest tests/agents/memory/test_provider.py` unmodified | existing |
| Observability: every action instrumented | `tests/retrieval/test_telemetry.py` parametrized over actions | new |
| Operability: unconfigured LanceDB is inert | `tests/retrieval/test_registry.py::test_missing_extra_is_unavailable` | new |
| Compatibility: embedding and rerank interfaces unchanged | `mypy` plus `tests/retrieval/test_shims.py` importing old paths | existing tooling, new test |

## Alternatives Considered

- Per-leg strategy generalization (proposal Approach 2): rejected because it forbids
  single-query hybrid with native filters, the property under evaluation.
- Whole-service adapter (proposal Approach 3): rejected because reranking, tree
  search, and aggregation would be duplicated per backend and memory could not share.
- Infino as the second adapter: deferred. Its 0.x API, single-writer rule, and
  Enterprise-only lakehouse integration make it a poorer first proof of the boundary
  than LanceDB. It is documented as a future adapter with the protocol mapping.
- A dedicated `delete` action: rejected in favor of `replace_parent` on `write` and
  reconciliation in `improve` (D7), keeping the four-action contract.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Parity regression hidden by a fixture that is too small | Baseline is recorded from the existing regression corpus across all three modes and both BM25 strategies; the golden test fails on any ordering change |
| Cold start of LanceDB on ephemeral Railway containers | Shadow read is post-response, so cold reads cannot affect users; the comparison record captures latency so the cost is measured, not guessed |
| Dual-write drift between Postgres and LanceDB | `improve` reconciles orphans; `retrieval-compare` reports overlap; drift is visible in both places |
| `operationalize-llm-evaluation-routing` edits `evaluation_service.py` concurrently | Retrieval metrics live in a new module; the service gains one method; the migration is additive with nullable columns |
| Memory tests encode raw SQL shapes | Tests in `tests/agents/memory/` are treated as a contract and must pass unmodified; the package scope denies writes to them |
| Alembic multiple heads | Migration task runs `alembic heads` first and merges if needed, per GOTCHAS |

## Task Decomposition Notes

Task titles containing "and" were audited. Titles split because they named two
outcomes: `RetrievalService` versus the facade (2.5 and 2.6), adapter write
implementation versus call-site routing (3.2 and 3.3), telemetry wrapper versus
diagnostics exposure (6.6 and 6.7). Titles retained with "and" name one outcome whose
description lists the scenarios a single test module covers (for example 1.1, 2.1,
4.1, 5.1, 6.1), or one adapter surface whose two verbs are inseparable (`write` and
`improve` on one adapter class, 3.2). No task is sized L or XL.

## Migration Plan

1. Land the protocol, models, settings, and migration with no behavior change.
2. Land the Postgres adapter and composition layer behind the parity golden test.
3. Route the write path and the memory consumer through the adapter.
4. Land LanceDB, dual-write, shadow read, and evaluation with every setting defaulting
   to off.
5. Enable `retrieval_secondary_adapter=lancedb` and `retrieval_shadow_read=true` in a
   staging profile; run `aca evaluate retrieval-compare` on a labeled dataset.

Rollback at any step is unsetting the retrieval settings. Shims in
`search_strategy.py` are removed one release after this change archives.
