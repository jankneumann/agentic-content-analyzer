# Change: agent-ergonomic-retrieval-surface

## Why

ACA's retrieval and workflow surfaces are consumed by LLM agents over MCP and HTTP. A design
review against the enterprise memory-platform specification (session log, 2026-09-05)
concluded that the specification's multi-step operating loop is not worth adopting here, but
four response-level properties are: results that state what they do not contain, safe paging,
evidence and staleness on derived records, and a small tool schema. Each maps to a verified gap:

1. **Search results overstate completeness.** `SearchResponse.total` is the size of the fused
   candidate window (`(limit + offset) * 5` chunks per strategy, capped at 500), not a corpus
   match count; deep pages re-run a larger query and reshuffle earlier pages. Reranking failure,
   embedding failure, and filter exclusion are all logged and discarded, while `meta` still
   advertises the rerank and embedding providers as if they ran. An agent reading this response
   asserts conclusions from a partial page with no signal that it is partial.
2. **Agents cannot page.** The MCP `search_content` tool exposes no `offset` or cursor, so an
   agent sees at most one page of at most 100 documents. `POST /api/v1/graph/query` returns
   `entities` and `relationships` with no total, no cursor, and no indication that `limit` was
   reached.
3. **Insights hide their evidence and never go stale.** `InsightResponse` drops
   `related_content_ids`, `related_theme_ids`, and `metadata`; the list route discards the total
   the service computes; and `agent_insights` has no maturity or supersession, so an insight
   from a regenerated digest is indistinguishable from a current one. The same insight is also
   stored twice, once in `agent_insights` and once in `agent_memories`.
4. **Pipeline runs are expensive and unpreviewable.** `pipeline.run` fans out into N
   `ingestion.execute` children plus `summarization.run` and `digest.create`, spending real LLM
   budget, and there is no way to see the child manifest or an estimated cost before submitting.
   The planning function `SourceRegistry.plan_scheduled_commands` is already side-effect free.
5. **The MCP tool schema is 41 tools, 19 of them `ingest_*` variants** hand-written from the
   same `COMMAND_FIELD_SCHEMAS` the capability document already publishes. Schema tokens are
   paid on every agent turn, and the variant count multiplies wrong-tool picks.

The owner has confirmed that ACA has a single consumer, so breaking changes that make the
contract cleaner are preferred over compatibility shims.

## What Changes

- **Search completeness and true totals** (**BREAKING**: `total` semantics and `SearchMeta`
  shape change):
  - `total` becomes the exact count of distinct documents that satisfy the lexical predicate
    and filters (one `COUNT` on the filter-scoped set; for vector-only searches it is the
    filter-eligible document count, since vector search ranks rather than matches);
  - `SearchMeta` gains `completeness` (`complete` | `truncated` | `degraded`) and
    `omissions: list[SearchOmission]` with typed reasons (`candidate_window_truncated`,
    `rerank_failed`, `rerank_partial`, `vector_unavailable`, `tree_search_fallback`,
    `filter_excluded`); `rerank_provider` and `embedding_provider` are reported only when they
    actually contributed;
  - `_build_meta` receives an execution record instead of only elapsed time.
- **Cursor paging** (**BREAKING**: `offset` removed from `SearchQuery`, `GET /api/v1/search`,
  and the frontend client):
  - `SearchQuery` gains `cursor: str | None`; `SearchResponse` gains `next_cursor: str | None`;
  - the cursor is an opaque, HMAC-signed keyset over a deterministic fused ranking computed once
    for up to `search_max_limit` documents and keyed by the query digest, so pages are stable;
  - MCP `search_content` gains `cursor` and returns `next_cursor`;
  - `GraphQueryResponse` gains `total_hits` and `truncated`; the route requests `limit + 1` to
    detect truncation because Graphiti exposes no offset.
- **Insight evidence and maturity** (**BREAKING**: list route returns an envelope):
  - `InsightResponse` exposes `related_content_ids`, `related_theme_ids`, `metadata`,
    `maturity`, `superseded_by`, `persona_name`;
  - `GET /api/v1/agent/insights` returns `{data, total, next_cursor}` with keyset paging and
    filters `maturity`, `min_confidence`, `tags`, matching the `agent-db-integration` spec that
    already describes those filters;
  - new columns `maturity` (`candidate` | `active` | `stale` | `superseded` | `withdrawn`,
    VARCHAR per house convention) and `superseded_by` on `agent_insights`;
  - `PATCH /api/v1/agent/insights/{id}` sets maturity or records supersession; supersession is
    a versioned successor link, never an in-place edit;
  - the conductor writes `candidate` when `confidence < 0.3` and `active` otherwise; when a
    digest is regenerated for the same period, insights from the prior digest become `stale`;
  - insights are stored once: the memory record becomes a pointer (`memory_type=insight`,
    `tags=["insight:<uuid>"]`, content = title plus summary) and recall filters out pointers
    whose insight is `superseded` or `withdrawn`. `MemoryFilter` gains `maturity`.
- **Pipeline dry run**:
  - `PipelineRequest.dry_run: bool = False`; when true, `POST /api/v1/pipeline-runs` returns
    `200 PipelinePlan` instead of `202 OperationHandle`: the planned source commands, the
    child-operation manifest in execution order, the idempotency key the real submission would
    derive, and `estimated_cost` with a per-step breakdown and its basis;
  - cost estimation uses `ModelConfig.calculate_cost` with the per-step model from
    `settings/models.yaml` and a token heuristic from the content-query preview count;
  - CLI `aca pipeline run --dry-run`; MCP `run_pipeline(dry_run=True)`;
  - `PipelinePlan` is added to the canonical contract and the generated models.
- **Collapsed MCP tool manifest** (**BREAKING**: 19 `ingest_*` tools removed):
  - one `ingest(source: str, params: dict | None, idempotency_key: str | None)` tool validated
    against `COMMAND_FIELD_SCHEMAS[source]` and dispatched through the same `_submit` path;
  - `CANONICAL_TOOL_NAMES` shrinks from 41 to 23; `get_capabilities` already carries the
    per-source field schema an agent needs to call `ingest`;
  - the conformance test asserts the new manifest and that every registry source is reachable
    through `ingest`; `MIGRATION.md` for the single external consumer records the mapping.

## Approaches Considered

### Approach 1: Clean contracts with cursors everywhere

Description: Replace offset paging with signed keyset cursors on search, insights, and MCP;
compute an exact `total`; return envelopes; collapse `ingest_*`. Accept the five breaking
points above and update the frontend client in the same change.

Pros:
- One paging idiom across HTTP, MCP, and the frontend; matches `OperationPage.next_cursor`.
- Completeness and omissions are structural, not bolted on.
- Smallest tool schema; `ingest` is derived from the registry the capability document already
  publishes, so the registry and the tool cannot drift.

Cons:
- Touches `web/` search and insights pages.
- Exact `total` costs one extra `COUNT` per search.

Effort: L, split into four M packages by boundary (search, insights, pipeline, MCP)

### Approach 2: Additive completeness, offset retained

Description: Keep `offset` and the current `total`, add `meta.completeness` and `omissions`,
add `offset` to the MCP tool, add insight fields to the existing response, add `dry_run`, and
gate `ingest_*` behind a tool profile instead of removing them.

Pros:
- No frontend changes; no consumer migration.

Cons:
- Deep paging stays unstable because the candidate window grows with `offset`.
- Two tool manifests to keep in conformance.
- `total` keeps lying; completeness has to explain a number the response should not carry.
- Rejected in discovery: the owner chose real `total` semantics and a real collapse.

Effort: M

### Approach 3: Context-pack endpoint over existing search

Description: Add a `POST /api/v1/context` that composes search, graph, and insights into one
bounded pack with completeness, leaving the underlying endpoints unchanged.

Pros:
- One call for agents; closest to the memory-platform `ContextPack`.

Cons:
- Hides rather than fixes the truncation and omission gaps in the underlying responses.
- Adds a composite surface without a consumer that needs the composition today.
- Cost estimation and tool collapse are unrelated to it and would still be separate work.

Effort: L

### Recommended

Approach 1. The owner has one consumer and prefers cleaner contracts; the only cost that does
not pay for itself is the extra `COUNT`, which is bounded by the filter scope and is the price
of a truthful `total`. Approach 3 is the memory-platform shape, but the review concluded the
multi-step loop is not the ergonomic gain here; the gain is in each response saying what it
omitted, which Approach 1 delivers at the source.

### Selected Approach

Approach 1 selected at Gate 1 on 2026-09-05 with no modifications. The owner confirmed ACA has
a single consumer, so the five breaking points (exact `total`, `offset` removed in favor of
cursors, insights list envelope, `ingest_*` collapse, `SearchMeta` shape) are accepted in
exchange for one paging idiom and a manifest that cannot drift from the source registry.
Approach 2 (additive, offset retained) and Approach 3 (context-pack over unchanged endpoints)
are recorded above for the reasons they were not chosen.

## Impact

Affected specs:
- MODIFIED `document-search`: Search API, Search Response Metadata
- MODIFIED `knowledge-graph`: HTTP graph query endpoint
- MODIFIED `agent-db-integration`: AgentInsightService, API Routes
- MODIFIED `agentic-analysis`: Memory Provider (maturity filter, single-store rule)
- MODIFIED `pipeline`: Single durable pipeline workflow (dry-run plan)
- MODIFIED `mcp-http-client`: MCP capability discovery, MCP workflow tools use canonical operations
- MODIFIED `specialist-tools`: Research Specialist Tool — `search_content`

Affected code:
- `src/services/search.py`, `src/models/search.py`, `src/api/search_routes.py`, `web/src/**/search*`
- `src/api/routes/graph_routes.py`, `src/api/schemas/graph.py`
- `src/models/agent_insight.py`, `src/services/agent_service.py`, `src/api/agent_routes.py`,
  `src/agents/conductor.py`, `src/agents/memory/models.py`, `web/src/**/insights*`
- `src/workflows/pipeline.py`, `src/contracts/workflow_models.py`, `src/api/operation_routes.py`
  (pipeline-runs route), `src/cli/workflow_commands.py`, `src/mcp_tools/workflows.py`
- `src/mcp_tools/ingestion.py`, `src/mcp_tools/toolsets.py`, `src/mcp_tools/content.py`,
  `src/mcp_tools/operations.py`, `tests/mcp/test_workflow_conformance.py`
- `openspec/contracts/content-workflows/openapi/v1.yaml` and generated models (`PipelinePlan`,
  `PipelineRequest.dry_run`)
- `alembic/versions/<new>_add_insight_maturity.py`
- `docs/SEARCH.md`, `docs/ACA-AGENTS.md`, `openspec/changes/.../MIGRATION.md`

Dependencies: `agent-runtime-correctness` must land first for the insight-maturity and
single-store rules (memory must run) and for `ModelConfig.calculate_cost` to be the only pricing
source used by the estimator. The search, graph, and MCP packages have no dependency on it.
