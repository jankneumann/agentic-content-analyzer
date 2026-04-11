# Tasks: Add HuggingFace Papers Ingestion Source

**Change ID**: `add-huggingface-papers-source`

## Parallelizability Notes

Tasks 1.1–1.3 can run in parallel (no file overlap). Phase 2 depends on Phase 1.
Phase 3 (tests) and Phase 4 (integration) can run in parallel after Phase 2.
Max parallel width: 4 (tasks 4.1–4.4 are independent of each other and of Phase 3).

---

## Phase 1: Core Implementation

- [x] 1.1 Add `HUGGINGFACE_PAPERS` to `ContentSource` enum
  **Spec scenarios**: hf-papers.1
  **Design decisions**: D1
  **Files**: `src/models/content.py` (modified)
  **Dependencies**: none

- [x] 1.2 Add `HuggingFacePapersSource` config model and discriminated union
  **Spec scenarios**: hf-papers.2
  **Design decisions**: D3
  **Files**: `src/config/sources.py` (modified)
  **Dependencies**: none

- [x] 1.3 Create Alembic migration for PG enum value
  **Spec scenarios**: hf-papers.1
  **Files**: `alembic/versions/b2c3d4e5f6a7_add_huggingface_papers_source.py` (created)
  **Dependencies**: none

## Phase 2: Ingestion Pipeline *(after Phase 1)*

- [x] 2.1 Implement `HuggingFacePapersClient` with link discovery and content extraction
  **Spec scenarios**: hf-papers.3, hf-papers.4, hf-papers.5, hf-papers.6
  **Design decisions**: D1, D3, D4
  **Files**: `src/ingestion/huggingface_papers.py` (created)
  **Dependencies**: 1.1

- [x] 2.2 Implement `HuggingFacePapersContentIngestionService` with 3-level dedup
  **Spec scenarios**: hf-papers.7, hf-papers.8, hf-papers.9, hf-papers.10
  **Design decisions**: D2, D4
  **Files**: `src/ingestion/huggingface_papers.py` (created)
  **Dependencies**: 1.1, 1.2

- [x] 2.3 Create source config YAML
  **Spec scenarios**: hf-papers.2
  **Files**: `sources.d/huggingface_papers.yaml` (created)
  **Dependencies**: 1.2

- [x] 2.4 Add orchestrator function
  **Spec scenarios**: hf-papers.11
  **Files**: `src/ingestion/orchestrator.py` (modified)
  **Dependencies**: 2.1, 2.2

- [x] 2.5 Add CLI command
  **Spec scenarios**: hf-papers.12, hf-papers.13
  **Files**: `src/cli/ingest_commands.py` (modified)
  **Dependencies**: 2.4

## Phase 3: Testing *(after Phase 2)*

- [x] 3.1 Write client unit tests (link discovery, content extraction, edge cases)
  **Spec scenarios**: hf-papers.3–6
  **Files**: `tests/test_ingestion/test_huggingface_papers.py` (created)
  **Dependencies**: 2.1

- [x] 3.2 Write service tests (dedup, persistence, error handling)
  **Spec scenarios**: hf-papers.7–10
  **Files**: `tests/test_ingestion/test_huggingface_papers.py` (created)
  **Dependencies**: 2.2

- [x] 3.3 Write config model tests
  **Spec scenarios**: hf-papers.2
  **Files**: `tests/config/test_huggingface_papers_sources.py` (created)
  **Dependencies**: 1.2

## Phase 4: Interface Integration *(parallel with Phase 3)*

- [ ] 4.1 Add MCP tool for agent invocation
  **Spec scenarios**: hf-papers.14
  **Design decisions**: D5
  **Files**: `src/mcp_server.py` (modified)
  **Dependencies**: 2.4

- [ ] 4.2 Add queue worker dispatch entry for HTTP API path
  **Spec scenarios**: hf-papers.15
  **Design decisions**: D5
  **Files**: `src/queue/worker.py` (modified)
  **Dependencies**: 2.4

- [ ] 4.3 Update API docstring to document huggingface_papers source
  **Spec scenarios**: hf-papers.15
  **Files**: `src/api/content_routes.py` (modified)
  **Dependencies**: none

- [ ] 4.4 Add frontend ingest UI support
  **Spec scenarios**: hf-papers.16, hf-papers.17
  **Design decisions**: D5
  **Files**: `web/src/types/content.ts` (modified), `web/src/routes/ingest.tsx` (modified)
  **Dependencies**: none

## Task Summary

| Phase | Tasks | Focus | Parallel Stream |
|-------|-------|-------|-----------------|
| 1. Core | 3 | Enum, config, migration | Stream A (parallel) |
| 2. Pipeline | 5 | Client, service, CLI | Stream A (sequential) |
| 3. Testing | 3 | Unit, service, config | Stream B (after Phase 2) |
| 4. Integration | 4 | MCP, queue, API, frontend | Stream C (parallel with Phase 3) |

## Dependency Graph (Critical Path)

```
1.1 ─┐
1.2 ─┼──▶ 2.1 ──▶ 2.2 ──▶ 2.4 ──▶ 2.5 ──▶ 3.1, 3.2
1.3 ─┘    2.3 ──────────────┼───────────────▶ 3.3
                             │
                             ├──▶ 4.1 (MCP tool)
                             └──▶ 4.2 (queue worker)
                     4.3 (API docs — independent)
                     4.4 (frontend — independent)
```
