# Contracts: retrieval-adapter-boundary

Contract sub-types evaluated for this change:

| Sub-type | Applies | Artifact |
|----------|---------|----------|
| OpenAPI | Yes, one schema delta | `openapi/search-meta.delta.yaml`. The search endpoints are not part of the canonical workflow contract at `openspec/contracts/content-workflows/openapi/v1.yaml`, so the Pydantic `SearchMeta` model in `src/models/search.py` is the wire authority; the delta is the reviewable record and is asserted by `tests/contract/test_search_meta_contract.py`. No `src/contracts/` regeneration applies. |
| Database | Yes, additive | `db/schema.sql` |
| Events | Yes, one structured log event | `events/retrieval-action.schema.json` |
| Type generation | Derived from the OpenAPI delta by the existing generator | not stored here |

## Adapter protocol (Python-level contract)

The adapter protocol is an in-process interface, not a wire contract, so it is
recorded here as a table rather than as OpenAPI.

| Action | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `write` | `(namespace, records: list[Record], *, replace_parent: bool = False)` | `WriteReport(written, replaced, failed)` | Upsert by id. `replace_parent=True` replaces every record sharing a parent id in the batch; an empty batch for a parent is a delete on adapters that own rows. |
| `search` | `(namespace, query: str, *, embedding: list[float] \| None, mode: bm25 \| vector \| hybrid, limit: int, filter: Filter)` | `LegResults(bm25: list[Candidate], vector: list[Candidate])` | Never fused, never reranked. `Candidate = (id, score, parent_id)`. |
| `read` | `(namespace, ids: list[int])` | `list[Record]` | Missing ids omitted. |
| `improve` | `(namespace)` | `ImproveReport(steps: list[(name, duration_ms)])` | Fold text index, compact or build vector index, reconcile orphans, drop retired tables. |
| `health_check` | `()` | `bool` | Never raises. |
| `supports` | `(namespace)` | `bool` | Deterministic, no backend call. |

Optional extension `SupportsAccessTracking.touch(namespace, ids)` updates access
statistics; implemented by Postgres for `agent_memories` only.

Filters are typed models: `ChunkFilter(source_types, publications, statuses,
chunk_types, date_from, date_to, content_ids)` and `MemoryFilter(memory_types, tags,
min_confidence, source_task_id, since)`. Adapters raise `UnsupportedFilterError`
for any field they cannot translate.

## Settings surface

| Setting | Default | Lock key |
|---------|---------|----------|
| `RETRIEVAL_PRIMARY_ADAPTER` | `postgres` | `env:retrieval-adapter-settings` |
| `RETRIEVAL_SECONDARY_ADAPTER` | unset | `flag:retrieval_secondary_adapter` |
| `RETRIEVAL_SHADOW_READ` | `false` | `flag:retrieval_shadow_read` |
| `RETRIEVAL_LANCEDB_URI` | unset | `env:retrieval-adapter-settings` |
| `RETRIEVAL_OBJECT_STORE_ENDPOINT` / `_REGION` / `_ACCESS_KEY_ID` / `_SECRET_ACCESS_KEY` | unset / `auto` / unset / unset | `env:retrieval-adapter-settings` |
| `RETRIEVAL_LANCEDB_VECTOR_INDEX_MIN_ROWS` | `50000` | `env:retrieval-adapter-settings` |
