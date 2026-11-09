# Tasks: retrieval-adapter-boundary

Sizes follow the plan-feature sizing table. No task is XL; none is L.
Spec scenario references use `<capability>.<Requirement>` names because the delta
specs use named scenarios rather than numbered ids.

## 1. Contracts, protocol, settings, migration

- [ ] 1.1 Write tests for retrieval models and protocol — record and filter models, namespace declaration, unsupported-namespace error, unsupported-filter-field error, `Candidate`/`LegResults` shapes
  **Spec scenarios**: retrieval-adapter.Retrieval Adapter Actions (read omits missing), retrieval-adapter.Retrieval Namespaces (declares support, unsupported rejected), retrieval-adapter.Typed Retrieval Filters (unsupported field rejected)
  **Contracts**: contracts/README.md (protocol table)
  **Design decisions**: D1, D3
  **Dependencies**: None
  **Files**: tests/retrieval/test_models.py, tests/retrieval/test_protocol.py
  **Size**: S

- [ ] 1.2 Implement retrieval package skeleton — `protocol.py`, `models.py`, `rrf.py` with the shared `weighted_rrf`
  **Dependencies**: 1.1
  **Files**: src/retrieval/__init__.py, src/retrieval/protocol.py, src/retrieval/models.py, src/retrieval/rrf.py
  **Size**: S

- [ ] 1.3 Write tests for retrieval settings — defaults off, unknown adapter rejected with known list, shadow without secondary rejected, secrets never in repr
  **Spec scenarios**: retrieval-adapter.Adapter Selection and Registry (default configuration, unknown adapter name)
  **Design decisions**: D11
  **Dependencies**: None
  **Files**: tests/config/test_retrieval_settings.py
  **Size**: S

- [ ] 1.4 Implement retrieval settings fields plus validator in `Settings`
  **Dependencies**: 1.3
  **Files**: src/config/settings.py
  **Size**: S

- [ ] Checkpoint: run tests, review diff, verify scope

- [ ] 1.5 Write migration test — single Alembic head, new columns and table present, routing datasets unaffected by defaults
  **Spec scenarios**: retrieval-evaluation.Retrieval Dataset Kind (operator creates), retrieval-adapter.Shadow Read (comparison recorded)
  **Contracts**: contracts/db/schema.sql
  **Design decisions**: D9, D10
  **Dependencies**: None
  **Files**: tests/alembic/test_retrieval_migration.py
  **Size**: S

- [ ] 1.6 Implement Alembic migration — `evaluation_datasets.dataset_kind`, `evaluation_samples.relevant_ids` and `provisional`, nullable `strong_model`/`weak_model`, `retrieval_shadow_comparisons` table; run `alembic heads` first and merge if needed
  **Dependencies**: 1.5
  **Files**: alembic/versions/<rev>_retrieval_adapter_boundary.py, src/models/evaluation.py, src/models/retrieval_shadow.py
  **Size**: S

- [ ] 1.7 Write a contract test asserting the `SearchMeta` wire shape matches `contracts/openapi/search-meta.delta.yaml` — the search endpoints are not in the canonical workflow OpenAPI contract, so the Pydantic model is the wire authority and the delta is the reviewable record
  **Spec scenarios**: document-search.Search Response Metadata (search response includes strategy metadata)
  **Contracts**: contracts/openapi/search-meta.delta.yaml
  **Dependencies**: None
  **Files**: tests/contract/test_search_meta_contract.py
  **Size**: S

- [ ] Checkpoint: run tests, review diff, verify scope

## 2. Postgres adapter extraction with parity

- [ ] 2.1 Record the parity baseline — a test that, before any refactor, captures ranked content ids and `meta` for the regression fixture across `bm25`, `vector`, `hybrid` and both BM25 strategies into `tests/retrieval/fixtures/parity_baseline.json`
  **Spec scenarios**: retrieval-adapter.Primary Adapter Parity (golden ranking preserved, BM25 strategy selection unchanged)
  **Design decisions**: D3, D4
  **Dependencies**: None
  **Files**: tests/retrieval/test_postgres_parity.py, tests/retrieval/fixtures/parity_baseline.json
  **Size**: M

- [ ] 2.2 Write tests for Postgres search legs — BM25 via both strategies, vector leg, filter translation to content-id list, empty filter short-circuit, mode limits legs
  **Spec scenarios**: retrieval-adapter.Retrieval Adapter Actions (per-leg candidates, mode limits legs), retrieval-adapter.Typed Retrieval Filters (applied before ranking, empty short-circuits)
  **Design decisions**: D2, D3
  **Dependencies**: 1.2
  **Files**: tests/retrieval/test_postgres_search.py
  **Size**: S

- [ ] 2.3 Implement Postgres search adapter — move both BM25 strategies and the pgvector query under `adapters/postgres/`; leave a re-export shim in `search_strategy.py`
  **Dependencies**: 2.2
  **Files**: src/retrieval/adapters/postgres/__init__.py, src/retrieval/adapters/postgres/adapter.py, src/retrieval/adapters/postgres/bm25.py, src/retrieval/adapters/postgres/vector.py, src/retrieval/adapters/postgres/filters.py, src/services/search_strategy.py
  **Size**: M

- [ ] Checkpoint: run tests, review diff, verify scope

- [ ] 2.4 Write tests for the composition layer — shared RRF identical across namespaces, reranking independent of adapter, tree search still runs, document aggregation unchanged
  **Spec scenarios**: retrieval-adapter.Composition Above the Adapter (all three scenarios)
  **Design decisions**: D2
  **Dependencies**: 1.2
  **Files**: tests/retrieval/test_service.py
  **Size**: S

- [ ] 2.5 Implement `RetrievalService` — fusion via `rrf.weighted_rrf`, rerank, tree search, document aggregation, highlight, consuming `LegResults`
  **Dependencies**: 2.3, 2.4
  **Files**: src/retrieval/service.py
  **Size**: M

- [ ] 2.6 Turn `HybridSearchService` into a facade over `RetrievalService`, populating `SearchMeta.retrieval_adapter`; constructor and `search()` signature unchanged
  **Spec scenarios**: document-search.Search Response Metadata (search response includes strategy metadata)
  **Design decisions**: D4
  **Dependencies**: 2.5, 2.1
  **Files**: src/services/search.py, src/models/search.py
  **Size**: S

- [ ] 2.7 Write the latency regression test — p95 of `query_time_ms` within 10 % of the recorded baseline on the regression fixture
  **Spec scenarios**: proposal NFR Performance
  **Dependencies**: 2.6
  **Files**: tests/regression/test_search_latency.py
  **Size**: S

- [ ] Checkpoint: run tests, review diff, verify scope; parity golden must pass

## 3. Write path through the adapter

- [ ] 3.1 Write tests for Postgres write and improve on `content_chunks` — idempotent embedding update with provenance, `replace_parent` semantics, orphan reconciliation, improve report with zero steps on second run
  **Spec scenarios**: retrieval-adapter.Retrieval Adapter Actions (write idempotent, improve reports its work)
  **Design decisions**: D6, D7
  **Dependencies**: 1.2
  **Files**: tests/retrieval/test_postgres_writes.py
  **Size**: S

- [ ] 3.2 Implement Postgres `write` and `improve` for `content_chunks` in `adapters/postgres/writes.py` — embedding and provenance update, `replace_parent`, orphan reconciliation, HNSW rebuild
  **Dependencies**: 3.1, 2.3
  **Files**: src/retrieval/adapters/postgres/writes.py (registered on the adapter through the write hook defined in 2.3, so `adapter.py` is not edited here)
  **Size**: S

- [ ] 3.3 Route the three write call sites through the registry's primary adapter so no raw embedding SQL remains outside the adapter
  **Design decisions**: D6, D7
  **Dependencies**: 3.2
  **Files**: src/services/indexing.py, src/scripts/backfill_chunks.py, src/scripts/switch_embeddings.py
  **Size**: M

- [ ] 3.4 Write tests for `aca manage optimize-index` — invokes improve per namespace, prints the report, JSON purity
  **Spec scenarios**: retrieval-adapter.Retrieval Adapter Actions (improve reports its work)
  **Dependencies**: 3.1
  **Files**: tests/cli/test_manage_optimize_index.py
  **Size**: S

- [ ] 3.5 Implement `aca manage optimize-index`
  **Dependencies**: 3.3, 3.4
  **Files**: src/cli/manage_commands.py
  **Size**: S

- [ ] Checkpoint: run tests, review diff, verify scope

## 4. Agent memory as a consumer

- [ ] 4.1 Write tests for the `agent_memories` namespace on the Postgres adapter — vector and keyword legs, memory filters, recency ordering, `touch` updates access statistics
  **Spec scenarios**: retrieval-adapter.Retrieval Namespaces (declares support), retrieval-adapter.Primary Adapter Parity (memory recall behavior preserved)
  **Design decisions**: D5
  **Dependencies**: 1.2
  **Files**: tests/retrieval/test_postgres_memory.py
  **Size**: S

- [ ] 4.2 Implement the `agent_memories` namespace and `SupportsAccessTracking` on the Postgres adapter
  **Dependencies**: 4.1, 2.3
  **Files**: src/retrieval/adapters/postgres/memory.py, src/retrieval/adapters/postgres/adapter.py
  **Size**: S

- [ ] 4.3 Rewire `VectorStrategy`, `KeywordStrategy`, and `MemoryProvider` fusion onto the adapter; every test under `tests/agents/memory/` passes unmodified
  **Spec scenarios**: retrieval-adapter.Primary Adapter Parity (memory recall behavior preserved)
  **Design decisions**: D2, D5
  **Dependencies**: 4.2
  **Files**: src/agents/memory/provider.py, src/agents/memory/strategies/vector.py, src/agents/memory/strategies/keyword.py
  **Size**: M

- [ ] Checkpoint: run tests, review diff, verify scope

## 5. LanceDB adapter and registry

- [ ] 5.1 Write tests for the LanceDB adapter on a local directory — write, hybrid search with filters, read, `replace_parent`, improve folds new rows into the text index, table naming per provider and dimension; skipped when the extra is absent
  **Spec scenarios**: retrieval-adapter.Object Storage Adapter (local directory table, new rows searchable after improve, deleted content removed)
  **Design decisions**: D7, D8
  **Dependencies**: 1.2
  **Files**: tests/retrieval/test_lancedb_adapter.py
  **Size**: M

- [ ] 5.2 Implement the LanceDB adapter
  **Dependencies**: 5.1
  **Files**: src/retrieval/adapters/lancedb/__init__.py, src/retrieval/adapters/lancedb/adapter.py, src/retrieval/adapters/lancedb/schema.py, src/retrieval/adapters/lancedb/filters.py
  **Size**: M

- [ ] 5.3 Write tests for the registry — lazy import, missing extra yields unavailable adapter with one warning, primary always Postgres, composite returned when secondary configured
  **Spec scenarios**: retrieval-adapter.Adapter Selection and Registry (secondary library missing)
  **Design decisions**: D12
  **Dependencies**: 1.4
  **Files**: tests/retrieval/test_registry.py
  **Size**: S

- [ ] 5.4 Implement the registry; add the `[lancedb]` extra to `pyproject.toml`
  **Dependencies**: 5.3, 5.2
  **Files**: src/retrieval/registry.py, pyproject.toml, uv.lock
  **Size**: S

- [ ] Checkpoint: run tests, review diff, verify scope

- [ ] 5.5 Write the object-store integration test — S3-compatible endpoint from settings, fresh process searches without a local copy; skipped without an endpoint
  **Spec scenarios**: retrieval-adapter.Object Storage Adapter (object store table)
  **Design decisions**: D11
  **Dependencies**: 5.2
  **Files**: tests/integration/test_lancedb_object_store.py
  **Size**: S

- [ ] 5.6 Implement object-store configuration in the LanceDB adapter using the retrieval object-store settings
  **Dependencies**: 5.5
  **Files**: src/retrieval/adapters/lancedb/adapter.py
  **Size**: S

## 6. Dual-write, shadow read, observability

- [ ] 6.1 Write tests for fail-safe dual write — secondary raise leaves primary committed, ingestion and backfill succeed, counts reported, embedding switch reaches both
  **Spec scenarios**: retrieval-adapter.Fail-Safe Dual Write (all three scenarios)
  **Design decisions**: D6, D13
  **Dependencies**: 1.2
  **Files**: tests/retrieval/test_dual_write.py
  **Size**: S

- [ ] 6.2 Implement `CompositeAdapter` in `dual_write.py`, returned by the registry when a secondary is configured
  **Dependencies**: 6.1, 5.4, 3.3
  **Files**: src/retrieval/dual_write.py, src/retrieval/registry.py
  **Size**: S

- [ ] 6.3 Write tests for shadow read — response returned before the shadow task starts, comparison row persisted with overlap and rank correlation, secondary failure silent, `meta.shadow` present only when enabled
  **Spec scenarios**: retrieval-adapter.Shadow Read (all three scenarios), document-search.Search Response Metadata (shadow metadata present only when shadow reading)
  **Design decisions**: D9
  **Dependencies**: 1.6, 2.6
  **Files**: tests/retrieval/test_shadow.py
  **Size**: S

- [ ] 6.4 Implement shadow scheduling and comparison persistence; populate `meta.shadow`
  **Dependencies**: 6.3, 6.2
  **Files**: src/retrieval/shadow.py, src/retrieval/service.py, src/models/search.py
  **Size**: S

- [ ] Checkpoint: run tests, review diff, verify scope

- [ ] 6.5 Write tests for telemetry — one structured event per action with adapter, namespace, action, count, duration; failure counters increment and appear in operations diagnostics
  **Spec scenarios**: retrieval-adapter.Retrieval Observability (both scenarios)
  **Contracts**: contracts/events/retrieval-action.schema.json
  **Design decisions**: D13
  **Dependencies**: 1.2
  **Files**: tests/retrieval/test_telemetry.py
  **Size**: S

- [ ] 6.6 Implement the telemetry wrapper with per-action structured events and in-process failure counters
  **Dependencies**: 6.5, 6.2
  **Files**: src/retrieval/telemetry.py
  **Size**: S

- [ ] 6.7 Expose the retrieval failure counters in the operations diagnostics response
  **Dependencies**: 6.6
  **Files**: src/api/operation_routes.py
  **Size**: S

## 7. Retrieval evaluation

- [ ] 7.1 Write tests for retrieval metrics — recall@5/10/20, MRR, top-k overlap, p50/p95, skipped samples with missing relevant ids
  **Spec scenarios**: retrieval-evaluation.Retrieval Metrics (both scenarios)
  **Dependencies**: None
  **Files**: tests/evaluation/test_retrieval_metrics.py
  **Size**: S

- [ ] 7.2 Implement `retrieval_metrics.py`
  **Dependencies**: 7.1
  **Files**: src/evaluation/retrieval_metrics.py
  **Size**: S

- [ ] 7.3 Write tests for the retrieval dataset kind — create from pairs, seed provisional from shadow comparisons, routing commands reject retrieval datasets
  **Spec scenarios**: retrieval-evaluation.Retrieval Dataset Kind (all three scenarios)
  **Design decisions**: D10
  **Dependencies**: 1.6
  **Files**: tests/evaluation/test_retrieval_datasets.py
  **Size**: S

- [ ] 7.4 Implement the retrieval dataset kind in the evaluation service — `create_retrieval_dataset`, `seed_from_shadow`, kind guard on `run_evaluation` and calibration, `run_retrieval_comparison`
  **Dependencies**: 7.3, 7.2
  **Files**: src/services/evaluation_service.py, src/models/evaluation.py
  **Size**: M

- [ ] Checkpoint: run tests, review diff, verify scope

- [ ] 7.5 Write tests for `aca evaluate retrieval-compare` and `create-dataset --kind retrieval` — results persisted per adapter and mode, unavailable adapter exits non-zero with nothing stored, JSON purity
  **Spec scenarios**: retrieval-evaluation.Retrieval Comparison Command (all three scenarios)
  **Dependencies**: 7.3
  **Files**: tests/cli/test_evaluate_retrieval.py
  **Size**: S

- [ ] 7.6 Implement the CLI commands
  **Dependencies**: 7.5, 7.4, 6.2
  **Files**: src/cli/evaluate_commands.py
  **Size**: S

## 8. Documentation

- [ ] 8.1 Update search documentation — adapter matrix with namespaces, storage targets, and known gaps; Infino and turbopuffer as future adapters with the protocol mapping; new settings and commands
  **Spec scenarios**: document-search.Cross-Backend Compatibility (backend compatibility documented)
  **Dependencies**: 6.7, 7.6
  **Files**: docs/SEARCH.md, docs/ACA-AGENTS.md
  **Size**: S

- [ ] 8.2 Record the decision — ADR under `docs/decisions/`, CLAUDE.md command list, GOTCHAS entry for "write means index write" and the memory test contract
  **Dependencies**: 8.1
  **Files**: docs/decisions/retrieval-adapter-boundary.md, CLAUDE.md, docs/GOTCHAS.md
  **Size**: S

## 9. Integration

- [ ] 9.1 Merge all packages, run the full suite, `ruff`, `mypy`, the parity golden, and the latency regression on the merged head
  **Dependencies**: 8.2
  **Files**: (none new)
  **Size**: M

- [ ] 9.2 Run `openspec validate retrieval-adapter-boundary --strict` and confirm every spec scenario maps to a passing test
  **Dependencies**: 9.1
  **Files**: (none new)
  **Size**: S
