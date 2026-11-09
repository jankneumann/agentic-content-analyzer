# Tasks: agent-ergonomic-retrieval-surface

Depends on `agent-runtime-correctness` for phases 4 and 5 (memory must run; one pricing
source). Phases 2, 3, and 6 have no dependency on it. Sizes per the Task Sizing Reference;
no task is L or XL.

## 1. Contracts

- [ ] 1.1 Write contract tests — `PipelinePlan` schema, `PipelineRequest.dry_run`, `SearchOmission`, `SearchMeta.completeness`, `SearchQuery.cursor` and `SearchResponse.next_cursor`, insights page envelope, generated models match (S)
  **Spec scenarios**: pipeline.3 (dry run returns a plan), document-search.4 (pagination support), document-search.10 (candidate window truncation)
  **Contracts**: contracts/openapi/v1.yaml
  **Design decisions**: D2, D3, D6
  **Dependencies**: None
  **Files**: tests/contract/test_canonical_workflow_contracts.py

- [ ] 1.2 Add the schemas and the `dry_run` 200 response to the canonical contract and regenerate with `make workflow-contracts` (M)
  **Dependencies**: 1.1
  **Files**: openspec/contracts/content-workflows/openapi/v1.yaml, src/contracts/workflow_models.py, web/src/generated/workflow-contracts.ts

- [ ] Checkpoint: run `make workflow-contracts-check` and contract tests, review diff, verify scope

## 2. Search completeness and cursors

- [ ] 2.1 Write service tests for exact `total` — hybrid, bm25, vector; with and without filters; count skipped when the window is smaller than `limit` (S)
  **Spec scenarios**: document-search.3 (response includes timing and exact total)
  **Design decisions**: D1
  **Dependencies**: None
  **Files**: tests/test_services/test_search_total.py

- [ ] 2.2 Write service tests for completeness and omissions — rerank failure, rerank partial, embedding failure, tree-search fallback, filter exclusion, candidate window truncation; providers reported only when they contributed (M)
  **Spec scenarios**: document-search.7 through document-search.11
  **Design decisions**: D2
  **Dependencies**: None
  **Files**: tests/test_services/test_search_completeness.py

- [ ] 2.3 Write service tests for signed cursors — deterministic ranking, no reappearance across pages, null on last page, digest mismatch rejected, tampered signature rejected (M)
  **Spec scenarios**: document-search.4, document-search.5
  **Design decisions**: D3
  **Dependencies**: None
  **Files**: tests/test_services/test_search_cursor.py

- [ ] 2.4 Implement `SearchExecution`, `SearchOmission`, the new `SearchMeta`, exact `total`, and `_rerank_chunks` returning status (M)
  **Dependencies**: 2.1, 2.2
  **Files**: src/services/search.py, src/models/search.py

- [ ] 2.5 Implement the signed keyset cursor in the service and remove `offset` (M)
  **Dependencies**: 2.3, 2.4
  **Files**: src/services/search.py, src/models/search.py

- [ ] 2.6 Write route tests — `GET`/`POST /api/v1/search` accept `cursor`, reject `offset` with 422, return `next_cursor` and `meta.completeness` (S)
  **Spec scenarios**: document-search.1, document-search.2, document-search.5
  **Contracts**: contracts/openapi/v1.yaml
  **Dependencies**: 1.2
  **Files**: tests/api/test_search_api.py

- [ ] 2.7 Update the search routes (S)
  **Dependencies**: 2.5, 2.6
  **Files**: src/api/search_routes.py

- [ ] Checkpoint: run `pytest tests/test_services tests/api/test_search_api.py -v`, review diff, verify scope

## 3. Graph truncation

- [ ] 3.1 Write route tests — `total_hits` and `truncated` on over-limit, exact-limit, and empty results (S)
  **Spec scenarios**: knowledge-graph.1 through knowledge-graph.4
  **Design decisions**: D4
  **Dependencies**: None
  **Files**: tests/api/test_graph_routes.py

- [ ] 3.2 Request `limit + 1` and add the two response fields (S)
  **Dependencies**: 3.1
  **Files**: src/api/routes/graph_routes.py, src/api/schemas/graph.py

## 4. Insight evidence, maturity, single store

- [ ] 4.1 Write migration test — columns added with defaults, existing rows `active`, downgrade drops both (S)
  **Contracts**: contracts/db/schema.sql
  **Design decisions**: D5
  **Dependencies**: None
  **Files**: tests/integration/test_insight_maturity_migration.py

- [ ] 4.2 Write the migration and the `InsightMaturity` enum (S)
  **Dependencies**: 4.1
  **Files**: alembic/versions/<rev>_add_insight_maturity.py, src/models/agent_insight.py

- [ ] 4.3 Write service tests — `create_insight` sets maturity from confidence, `list_insights` keyset paging plus `maturity`, `min_confidence`, and `tags` filters, `set_maturity` rejects `superseded`, `supersede` preserves content, `mark_stale_for_schedule` (M)
  **Spec scenarios**: agent-db-integration.1 through agent-db-integration.6
  **Design decisions**: D5
  **Dependencies**: None
  **Files**: tests/agents/test_insight_service.py

- [ ] 4.4 Implement the service methods (M)
  **Dependencies**: 4.2, 4.3
  **Files**: src/services/agent_service.py

- [ ] 4.5 Write route tests — insights envelope with `total` and `next_cursor`, full evidence fields, `PATCH` validation matrix (S)
  **Spec scenarios**: agent-db-integration.11, agent-db-integration.12, agent-db-integration.13
  **Contracts**: contracts/openapi/v1.yaml
  **Dependencies**: 1.2
  **Files**: tests/agents/test_api_routes.py

- [ ] 4.6 Implement the insight routes and response model (S)
  **Dependencies**: 4.4, 4.5
  **Files**: src/api/agent_routes.py

- [ ] 4.7 Write conductor and memory tests — insight stored once as a pointer, `metadata.schedule_id` set for scheduled tasks, prior-run insights become stale, recall drops superseded and withdrawn, `MemoryFilter.maturity` (M)
  **Spec scenarios**: agentic-analysis.7 (insights stored once), agentic-analysis.8 (recall filters by maturity)
  **Design decisions**: D5
  **Dependencies**: None
  **Files**: tests/agents/test_conductor.py, tests/agents/memory/test_provider.py

- [ ] 4.8 Implement the pointer store in the conductor, the stale marking on scheduled reruns, and the maturity-aware recall filter (M)
  **Dependencies**: 4.4, 4.7
  **Files**: src/agents/conductor.py, src/agents/memory/models.py, src/agents/memory/provider.py, src/agents/memory/strategies/keyword.py, src/agents/memory/strategies/vector.py

- [ ] Checkpoint: run `pytest tests/agents tests/integration/test_insight_maturity_migration.py -v`, review diff, verify scope

## 5. Pipeline dry run

- [ ] 5.1 Write workflow tests — `PipelinePlan` fields, child manifest order, idempotency key equals the real derivation, no job enqueued, empty sources returns `pipeline_no_sources`, estimate uses `ModelConfig.calculate_cost` and declares its basis (M)
  **Spec scenarios**: pipeline.3, pipeline.4, pipeline.5
  **Contracts**: contracts/openapi/v1.yaml
  **Design decisions**: D6
  **Dependencies**: 1.2
  **Files**: tests/workflows/test_pipeline_plan.py

- [ ] 5.2 Implement `PipelinePlanner` (plan plus estimator) in the pipeline workflow module (M)
  **Dependencies**: 5.1
  **Files**: src/workflows/pipeline.py, src/workflows/pipeline_plan.py

- [ ] 5.3 Write surface tests — HTTP returns 200 `PipelinePlan` on `dry_run`, CLI `--dry-run` prints one JSON document to stdout, MCP `run_pipeline(dry_run=True)` returns the plan (S)
  **Spec scenarios**: pipeline.3, mcp-http-client.5
  **Dependencies**: 5.2
  **Files**: tests/api/test_operation_routes.py, tests/cli/test_pipeline_dry_run.py, tests/mcp/test_workflow_conformance.py

- [ ] 5.4 Wire the HTTP route, CLI flag, and MCP parameter (S)
  **Dependencies**: 5.3
  **Files**: src/api/operation_routes.py, src/cli/workflow_commands.py, src/mcp_tools/workflows.py

- [ ] Checkpoint: run `pytest tests/workflows tests/api/test_operation_routes.py tests/cli/test_pipeline_dry_run.py -v`, review diff, verify scope

## 6. MCP manifest collapse

- [ ] 6.1 Rewrite the conformance tests — 23-name manifest, every registry key round-trips through `ingest`, unknown source raises a typed protocol error, unknown params rejected, `search_content` accepts `cursor`, `get_capabilities.supported_tools` matches (M)
  **Spec scenarios**: mcp-http-client.1 through mcp-http-client.6
  **Design decisions**: D7, D8
  **Dependencies**: None
  **Files**: tests/mcp/test_workflow_conformance.py

- [ ] 6.2 Implement `ingest`, delete the 19 `ingest_*` tools, update the manifest (M)
  **Dependencies**: 6.1
  **Files**: src/mcp_tools/ingestion.py, src/mcp_tools/toolsets.py, src/mcp_tools/operations.py

- [ ] 6.3 Add `cursor` to `search_content` and update the specialist `search_content` tool to append the completeness line (S)
  **Spec scenarios**: specialist-tools.1, specialist-tools.2
  **Dependencies**: 2.5, 6.1
  **Files**: src/mcp_tools/content.py, src/agents/specialists/tools/research.py

- [ ] 6.4 Write `MIGRATION.md` mapping each removed `ingest_*` tool to `ingest(source=...)` and listing the `offset` and insights-envelope changes (S)
  **Dependencies**: 6.2
  **Files**: openspec/changes/agent-ergonomic-retrieval-surface/MIGRATION.md

- [ ] Checkpoint: run `pytest tests/mcp -v`, review diff, verify scope

## 7. Frontend

- [ ] 7.1 Write E2E tests — search page pages with `next_cursor` and shows a completeness notice on truncated or degraded results; insights page reads the envelope and shows maturity (M)
  **Spec scenarios**: document-search.4, agent-db-integration.11
  **Dependencies**: 1.2
  **Files**: web/tests/e2e/search-paging.spec.ts, web/tests/e2e/insights-maturity.spec.ts

- [ ] 7.2 Update the search and insights pages and API client (M)
  **Dependencies**: 7.1, 2.7, 4.6
  **Files**: web/src/**/search*, web/src/**/insights*, web/src/generated/workflow-contracts.ts

## 8. Integration and documentation

- [ ] 8.1 Run the gen-eval search and pipeline scenarios against the reduced tool surface and record calls, tokens, and success per task in the validation report (M)
  **Dependencies**: 2.7, 5.4, 6.3
  **Files**: evaluation/scenarios/agent-retrieval-surface.yaml, openspec/changes/agent-ergonomic-retrieval-surface/validation-report.md

- [ ] 8.2 Update `docs/SEARCH.md`, `docs/ACA-AGENTS.md`, and `docs/API_CONSUMERS.md` (S)
  **Dependencies**: 8.1
  **Files**: docs/SEARCH.md, docs/ACA-AGENTS.md, docs/API_CONSUMERS.md

- [ ] 8.3 Run the full suite, E2E, and the contract drift check (S)
  **Dependencies**: 8.2, 7.2
  **Files**: none
