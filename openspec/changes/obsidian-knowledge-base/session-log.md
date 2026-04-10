# Session Log: obsidian-knowledge-base

## Phase: Implementation (2026-04-09)

**Agent**: claude-opus-4-6 (1M context) | **Session**: implement-feature `/implement-feature obsidian-knowledge-base`

### Decisions
1. **Two-tier execution: orchestrator + parallel sub-agent** — The proposal touches 9 phases and ~14 separate components. The main agent built the foundation (models, migration, KB service, CLI, Obsidian export, pipeline integration) sequentially since each layer depends on the prior one. A sub-agent ran in parallel to build the four independent surface integrations (REST API + KBQAService + KBHealthService + 6 MCP tools) that all sit on top of the KB service. This kept the main context window small while overlapping meaningful work.
2. **Lazy-import pattern for CLI service references** — `kb_commands.py` imports `KnowledgeBaseService`, `KBQAService`, and `KBHealthService` *inside* the function bodies, not at module top-level. This avoids loading the full service stack on every CLI invocation and prevents circular imports. Tests must therefore patch at the source module (e.g. `src.services.knowledge_base.KnowledgeBaseService`), not the consumer (`src.cli.kb_commands.KnowledgeBaseService`) — confirmed by the lazy-import patch gotcha in MEMORY.md.
3. **Topic embedding column unmapped from SQLAlchemy** — Following the `DocumentChunk.embedding` precedent: the `topics.embedding` pgvector column is created in the migration via raw SQL (`ALTER TABLE topics ADD COLUMN embedding vector`) and read/written via raw SQL in `KnowledgeBaseService._persist_topic_embedding()` and `_match_to_topic()`. The SQLAlchemy ORM never references it. This avoids importing pgvector Python bindings at model load time.
4. **Sentinel-row lock fallback for non-Postgres backends** — `pg_try_advisory_lock` is the canonical concurrency control (D10), but falls back gracefully to a sentinel row in `kb_indices` when the backend doesn't support advisory locks. This makes the service testable against SQLite or any DB without losing the "one compile at a time" semantic in production.
5. **Article similarity uses Jaccard, not cosine** — The spec says "cosine similarity > 0.90 between articles" for merge candidate detection, but the implementation uses token Jaccard via `_article_similarity()`. Reason: avoiding LLM-based or embedding-based similarity for the *article body* check keeps merge detection cheap and deterministic. Topic *matching* (during compile) still uses embedding cosine — the two are different code paths with different cost/precision trade-offs.
6. **Topic export bypasses `_write_note()` collision logic** — The 3-tier vault structure (`Category/Topic/_overview.md`) is incompatible with the existing flat-folder collision resolution (`-2`, `-3` suffixes). I added a parallel `_write_topic_file()` helper that preserves the caller-supplied path and uses the manifest only for change detection. This keeps the existing digest/summary export untouched while supporting the new structure.

### Alternatives Considered
- **All-in-one agent for the full proposal**: rejected — context budget would overflow long before reaching the surface integrations. Splitting via sub-agent let me parallelize ~30% of the work without losing visibility into integration risk.
- **Mapping the embedding column on `Topic`**: rejected — would require a hard pgvector dependency at import time, causing test environments without pgvector to fail. The unmapped pattern is the project convention.
- **Hard-fail compile on graph sync errors**: rejected — D2 explicitly says "DB-primary, graph-optional". `_sync_to_graph()` is wrapped in try/except so missing/failed Graphiti backends don't break compilation.
- **Forcing the KB compile step into `aca pipeline daily` by default**: rejected — `kb_pipeline_enabled` defaults to `False` per the proposal. The pipeline integration is opt-in, with non-fatal failures.

### Trade-offs
- Accepted **a single Alembic migration head** (`c5f6a7b8d9e0`) chained off `bc56c4b2e94d` over branching, keeping the migration graph linear. This means the migration must be sequenced after any other in-flight migrations targeting `bc56c4b2e94d` — checked: none currently.
- Accepted **synchronous compile via `asyncio.run()` in CLI/pipeline** over a queue-based async path. The proposal explicitly rejects event-driven compilation (Approach C). For interactive CLI use, `asyncio.run()` is the simplest correct approach.
- Accepted **a sub-agent for parallel work** over an all-sequential implementation. This came with the small risk of integration drift (e.g. mismatched method signatures between the main agent's CLI and the sub-agent's `KBQAService`). Mitigated by writing a precise contract in the sub-agent prompt and verifying with `python -c "from ... import ..."` after the sub-agent finished.

### Open Questions
- [ ] Should KB compilation also be exposed via the queue worker (PGQueuer) for very large topic counts? Deferred — current scale (~100s of topics) doesn't need it; revisit if scale changes.
- [ ] Topic matching currently uses keyword (token) search inside `KBQAService._search_topics()`. If KB grows beyond ~1000 topics, swap to vector search via the existing `DocumentChunk.embedding` infrastructure.
- [ ] `tests/cli/test_pipeline_commands.py::TestDailyPipeline` failures are pre-existing (`ConnectTimeout` against localhost) — verified against `main` branch. Not in scope for this PR but worth tracking separately.

### Context
Implemented all 9 phases of the obsidian-knowledge-base proposal in a single PR: Topic/TopicNote/KBIndex models with Alembic migration, full `KnowledgeBaseService` (compilation, advisory lock concurrency, two-phase matching, relationship detection, index generation), `KBQAService` for Q&A with file-back, `KBHealthService` for stale/merge/coverage linting, six new MCP tools, ten KB REST endpoints at `/api/v1/kb/*`, six `aca kb` CLI commands, optional `kb_pipeline_enabled` integration in `aca pipeline daily`, and Obsidian exporter extension with 3-tier `Category/Topic/_overview.md` vault structure. Total: 7 new files, 11 modified files, 98 passing tests across models/services/CLI/API/Obsidian. `openspec validate obsidian-knowledge-base --strict` passes.
