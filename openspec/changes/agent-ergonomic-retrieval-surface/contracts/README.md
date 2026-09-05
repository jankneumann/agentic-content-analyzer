# Contracts: agent-ergonomic-retrieval-surface

| Sub-type | Applies | Artifact |
|---|---|---|
| OpenAPI | Yes | `openapi/v1.yaml` — `PipelinePlan` and `PipelineRequest.dry_run` merge into the canonical contract; the search, graph, and insights shapes are recorded here so the generated TypeScript client covers them (they are FastAPI-only today) |
| Database | Yes | `db/schema.sql` — two columns and two indexes on `agent_insights` |
| Events | No | No new event payloads; `OperationEvent` is unchanged because a dry run emits no operation |
| Generated types | Via `make workflow-contracts` | `src/contracts/workflow_models.py`, `web/src/generated/workflow-contracts.ts` |

Breaking points recorded for the single consumer (see `MIGRATION.md`, task 6.4):
`SearchQuery.offset` removed, `SearchResponse.total` semantics, `SearchMeta` shape,
`GET /api/v1/agent/insights` envelope, and the 19 `ingest_*` MCP tools replaced by `ingest`.
