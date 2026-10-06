# Design: agent-ergonomic-retrieval-surface

## Context

Agents consume ACA through the MCP server (`src/mcp_tools/`) and the HTTP API. The review
that produced this change concluded that the enterprise memory platform's multi-step
operating loop is not the ergonomic gain for a single-owner system; four response-level
properties are. Each property maps to a verified defect:

- `HybridSearchService.search()` over-fetches `(limit + offset) * 5` chunks per strategy,
  fuses them, and reports `total = len(sorted_docs)`, the fused window size. Rerank failure,
  embedding failure, tree-search fallback, and filter exclusion are logged and dropped;
  `_build_meta(elapsed_ms)` is a snapshot of static configuration.
- `search_content` (MCP) exposes no `offset`; `GraphQueryResponse` has no total or cursor,
  and `limit` is a combined cap across entities and relationships.
- `InsightResponse` drops evidence fields; the list route discards the total; `agent_insights`
  has no lifecycle; the conductor writes each insight to both `agent_insights` and
  `agent_memories`.
- `pipeline.run` fans out into N `ingestion.execute` children plus `summarization.run` and
  `digest.create` with no preview; `SourceRegistry.plan_scheduled_commands` is already pure.
- `CANONICAL_TOOL_NAMES` has 41 entries, 19 of them hand-written `ingest_*` variants of the
  same `COMMAND_FIELD_SCHEMAS` that `get_capabilities` already publishes; the manifest check
  is order-sensitive and import-time.

This change depends on `agent-runtime-correctness` for a running memory provider (D5's
single-store rule) and for `ModelConfig.calculate_cost` being the only pricing source (D6).
The owner confirmed one consumer, so breaking changes that simplify contracts are preferred.

## Goals / Non-Goals

Goals:
- Every retrieval response states its completeness and typed omissions.
- One paging idiom (signed keyset cursor) across search, insights, and MCP.
- Insights expose evidence, carry a maturity axis, and are stored once.
- Pipeline runs can be previewed with a child manifest and cost estimate.
- The MCP manifest shrinks to 23 tools with one registry-driven `ingest` tool.

Non-Goals:
- A composite context-pack endpoint.
- Changing ranking, RRF constants, or reranker selection.
- Cursor paging on `GET /api/v1/agent/tasks` (offset retained; not an agent surface).
- Tool profiles or per-agent tool subsets.
- Knowledge-base topic search changes (`/api/v1/kb/search` keeps its own scoring).

## Decisions

### D1: `total` is an exact filter-scoped count

`total` becomes the number of distinct `content` rows that could appear in the result for the
request: when BM25 participates (`hybrid` or `bm25`), the count of documents with at least one
chunk matching the lexical predicate under the filters; for `vector`, the count of
filter-eligible documents with at least one embedded chunk, because vector search ranks rather
than matches. Both are one `COUNT(DISTINCT content_id)` against the same filter resolution the
strategies use (`_resolve_content_filter`). The count is computed after the strategies run so
it can be skipped when the fused window is smaller than `limit` (then `total` equals the window
size and `completeness` is `complete`).

### D2: Completeness and omissions are structural

```python
class SearchOmission(BaseModel):
    reason: Literal[
        "candidate_window_truncated", "rerank_failed", "rerank_partial",
        "vector_unavailable", "tree_search_fallback", "filter_excluded",
    ]
    detail: str | None = None
    affected: int | None = None   # documents or chunks, per reason

class SearchMeta(BaseModel):
    completeness: Literal["complete", "truncated", "degraded"]
    omissions: list[SearchOmission]
    bm25_strategy: str
    embedding_provider: str | None   # None when the vector arm did not contribute
    embedding_model: str | None
    rerank_provider: str | None      # None when reranking did not run to completion
    rerank_model: str | None
    query_time_ms: int
    backend: str
```
`completeness` is `degraded` when any strategy or reranker failed, `truncated` when the fused
window was smaller than `total` or the reranker covered fewer candidates than the window, and
`complete` otherwise. A `SearchExecution` record accumulates these facts inside `search()` and
is passed to `_build_meta`. `_rerank_chunks` returns `(scores, status)` instead of disguising a
fallback as success.

### D3: Signed keyset cursor over a deterministic ranking

`SearchQuery.offset` is removed; `SearchQuery.cursor: str | None` is added; `SearchResponse`
gains `next_cursor`. On the first page the service fuses up to `search_max_limit` documents
once, in deterministic order `(-score, content_id)`, and encodes the cursor as
`base64url(HMAC(secret, query_digest | ranking_version | last_score | last_content_id))` plus
the plain fields. A cursor whose `query_digest` (canonical JSON of query, type, filters,
weights) does not match the request returns `422 invalid_cursor`. Because pages are cut from
the same ranking, no page reshuffles. The HMAC key reuses `_history_cursor_signing_key` from
the operations service. `GET /api/v1/search` accepts `cursor`; the frontend search page moves
from offset to `next_cursor`.

### D4: Graph truncation flag

`GraphQueryRequest` is unchanged. The route requests `limit + 1` from Graphiti and returns
`GraphQueryResponse{entities, relationships, total_hits, truncated}` where `total_hits` is the
number of raw hits returned (capped at `limit + 1`) and `truncated` is true when the extra hit
was present. Graphiti has no offset, so no cursor is offered; the response says so instead of
implying completeness.

### D5: Insight evidence, maturity, supersession, single store

Columns on `agent_insights`: `maturity VARCHAR NOT NULL DEFAULT 'active'` (values `candidate`,
`active`, `stale`, `superseded`, `withdrawn`) and `superseded_by UUID NULL REFERENCES
agent_insights(id)`. `InsightMaturity` StrEnum is the source of truth. Rules:
- the conductor writes `candidate` for `confidence < 0.3`, else `active`;
- when a scheduled task runs again for the same `schedule_id`, insights from that schedule's
  previous run move to `stale` (the conductor stores `metadata.schedule_id` from task params);
- `PATCH /api/v1/agent/insights/{id}` accepts `{maturity}` or `{superseded_by}`; setting
  `superseded_by` sets `maturity = superseded` on the target and never edits content;
- the memory record for an insight is a pointer: `memory_type = insight`,
  `tags = ["insight:<uuid>", ...]`, `content = title + "\n" + first 500 chars`; recall joins
  on the pointer and drops `superseded` and `withdrawn` insights; `MemoryFilter.maturity`
  filters the rest.
`GET /api/v1/agent/insights` returns `{data, total, next_cursor}` with keyset paging on
`(created_at, id)` and the filters the spec already lists (`maturity`, `min_confidence`,
`tags`). `InsightResponse` adds `related_content_ids`, `related_theme_ids`, `metadata`,
`maturity`, `superseded_by`, `persona_name`.

### D6: Pipeline dry run returns a plan, not a handle

`PipelineRequest.dry_run: bool = False`. When true, `POST /api/v1/pipeline-runs` returns
`200 PipelinePlan`:
```yaml
PipelinePlan:
  schema_version: 1
  request: PipelineRequest         # dry_run echoed as true
  idempotency_key: string          # what the real submission would derive
  source_commands: [IngestCommand] # from plan_scheduled_commands
  child_operations:                # execution order
    - { operation_type: ingestion.execute, ordinal: 1, source_key: src_… }
    - { operation_type: summarization.run, ordinal: N+1 }
    - { operation_type: digest.create, ordinal: N+2 }
  estimated_cost:
    total_usd: number
    basis: { content_count: int, avg_input_tokens: int, avg_output_tokens: int, pricing_source: models.yaml }
    steps:
      - { step: summarization, model_id, provider, calls, usd }
      - { step: digest_creation, model_id, provider, calls, usd }
```
`content_count` comes from the content-query preview for the period; token averages come from
the last 30 days of `llm_usage` when available, else registry defaults. Cost uses
`ModelConfig.calculate_cost` only. The plan is not persisted and no job is enqueued. CLI:
`aca pipeline run --dry-run`; MCP: `run_pipeline(dry_run=True)` returns `PipelinePlan`.

### D7: One registry-driven `ingest` tool

```python
async def ingest(source: str, params: dict[str, Any] | None = None,
                 idempotency_key: str | None = None) -> OperationHandle
```
`source` must be a `SOURCE_REGISTRY` key; `params` is validated against
`COMMAND_FIELD_SCHEMAS[source]` with unknown keys rejected, then dispatched through the existing
`_submit`. The 19 `ingest_*` functions and `INGESTION_TOOL_BY_SOURCE` are deleted.
`CANONICAL_TOOL_NAMES` becomes 23 names; the conformance test asserts every registry source is
invocable through `ingest` with its schema fields, replacing the per-signature parity test.
`get_capabilities` is unchanged in shape and already carries the per-source fields.

### D8: MCP search paging

`search_content` gains `cursor: str | None` and returns the full `SearchResponse`, including
`next_cursor` and `meta.completeness`. The tool docstring tells the agent to page only when
`completeness != "complete"` or `next_cursor` is set.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Keep offset and add completeness only | Deep paging stays unstable; `total` keeps lying. Rejected in discovery. |
| Tool profiles hiding `ingest_*` | Two manifests to keep in conformance; the collapse removes the drift surface entirely. |
| Unsigned cursor (plain base64) | A client could forge a position past the ranking window or across a different query; signing costs one HMAC. |
| Exact `total` via per-strategy `COUNT` inside each strategy | Duplicates the filter logic; one count against the resolved filter set is simpler. |
| Insight lifecycle as an event table | Over-engineered for one owner; a maturity column plus a successor link covers supersession and staleness. |
| Persist `PipelinePlan` as an operation with status `planned` | Adds a non-executing job to the queue; a plan is a response, not a durable resource. |

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Exact `COUNT` is slow on large corpora | Skipped when the fused window is smaller than `limit`; bounded by the filter set; indexed on `content_id`. |
| Frontend search and insights pages break | `wp-frontend` updates both pages and the generated client in the same change; E2E covers paging. |
| External MCP consumer loses `ingest_*` | `MIGRATION.md` maps each old tool to `ingest(source=...)`; owner confirmed single consumer. |
| Cost estimate is wrong | The plan labels its basis and pricing source; the estimate is advisory and never gates submission. |
| Stale marking hits insights the owner still wants | `stale` is a filterable state, never a deletion; `PATCH` can restore `active`. |
| Ranking version changes invalidate cursors | `ranking_version` is in the signed payload; mismatch returns `422 invalid_cursor`, and the agent restarts from page one. |

## Migration Plan

1. `wp-contracts` adds `PipelinePlan`, `PipelineRequest.dry_run`, `SearchOmission`, cursor
   fields, and the insights envelope to the canonical contract; regenerate.
2. `wp-search`, `wp-insights`, `wp-pipeline-plan`, and `wp-mcp` run in parallel on disjoint
   scopes; `wp-frontend` follows `wp-search` and `wp-insights`.
3. Migration adds the two insight columns with defaults; existing rows become `active`.
4. Rollback: revert the manifest to 41 names (the old functions are in git history), drop the
   two columns, and restore `offset` in the generated client.
