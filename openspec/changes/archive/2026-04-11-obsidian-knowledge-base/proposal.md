# Proposal: Obsidian Knowledge Base

## Status

DRAFT

## Why

The newsletter aggregator ingests content from 10+ sources and produces daily/weekly digests — but knowledge stays ephemeral. ThemeAnalysis identifies trends across content, yet those insights exist only as embedded JSON in analysis records. There is no persistent, queryable, evolving knowledge entity.

Karpathy's LLM-compiled knowledge base approach demonstrates that LLMs can maintain structured knowledge bases where topics are first-class entities with compiled articles, self-maintained indices, and health checks. Our system already has the raw material (content, summaries, themes) and the infrastructure (hybrid search, knowledge graph, MCP tools) — what's missing is the compilation step that promotes ephemeral themes into persistent, evolving topics.

Additionally, the Obsidian vault exporter (just merged via PR #371) currently exports digests, summaries, and theme MOCs — but not compiled topic articles. Extending it to export Topic entities in the 3-tier vault structure (Category/Topic/Source) turns Obsidian from a simple export target into a genuine knowledge base interface.

## What Changes

### Phase 1: Data Model & Compilation

1. **Topic + TopicNote SQLAlchemy models** with Alembic migration — persistent, versioned knowledge entities that promote ThemeData from ephemeral JSON to first-class DB records
2. **KB compilation service** — incremental LLM-driven compilation that gathers new evidence (themes, summaries, content), matches to existing topics (exact + semantic), compiles/recompiles article markdown, detects relationships and hierarchies
3. **Index generation service** — auto-maintained master, category, trend, and recency indices (cached markdown + dynamic queries)
4. **CLI commands** (`aca kb compile|list|show|index`) — full KB management from the command line
5. **Settings + prompts YAML** — `MODEL_KB_COMPILATION`, `MODEL_KB_INDEX` following existing `MODEL_*` pattern; prompt templates for compilation, indexing, relationship detection

### Phase 2: Q&A, Health, API, MCP

6. **KB Q&A mode** — agent answers questions against compiled KB (not raw content), optionally files answers as TopicNotes
7. **Health check / linting service** — stale detection, consistency checks, coverage gaps, merge candidates, missing connections, article quality scoring
8. **API endpoints** (`/api/v1/kb/topics`, `/compile`, `/health`, `/query`, `/index`) — full REST interface with pagination
9. **MCP tools** (`get_topic`, `update_topic`, `add_topic_note`, `get_kb_index`, `compile_knowledge_base`, `search_knowledge_base`) — agent-accessible KB interface

### Obsidian Exporter Extension

10. **Update obsidian_exporter.py** to export Topic `_overview.md` files in the 3-tier vault structure (Category/Topic/Source with source extracts linking to summaries/content)

### Graph Integration (Optional)

11. **DB-primary, graph-optional relationships** — `related_topic_ids` JSON column and `parent_topic_id` FK as canonical store; optional Graphiti sync when graph backend is available (graceful degradation)

## Impact

### New Specs
- **knowledge-base** — new capability spec for KB compilation, topics, indices, health

### Existing Specs Consumed (Read-Only)
- **theme-analysis** — Topic compilation consumes ThemeAnalysis output (no spec changes needed)
- **document-search** — Topics reuse existing hybrid search infrastructure (no spec changes needed)

### Note on Spec Scope
CLI commands, API endpoints, MCP tools, pipeline integration, and Obsidian export are all covered within the new knowledge-base spec. No modifications to existing specs are required.

### Modified Code
- `src/sync/obsidian_exporter.py` — extend with Topic export
- `src/sync/obsidian_frontmatter.py` — add Topic frontmatter format
- `src/mcp_server.py` — add KB MCP tools
- `src/cli/` — add `kb_commands.py`
- `src/api/app.py` — mount KB router
- `settings/prompts.yaml` — add KB compilation prompts
- `settings/models.yaml` — add KB model defaults

### New Code
- `src/models/topic.py` — Topic, TopicNote, TopicStatus
- `src/services/knowledge_base.py` — KB compilation service
- `src/services/kb_index.py` — index generation
- `src/services/kb_health.py` — health checks / linting
- `src/services/kb_qa.py` — Q&A agent mode
- `src/api/kb_routes.py` — API endpoints
- `alembic/versions/*_add_topic_tables.py` — migration

## Non-Goals

- **Obsidian Mode 1 (CLI-driven)** — requires Obsidian 1.12+ which is not yet widely available
- **Obsidian Mode 3 (headless sync)** — server-side sync requires obsidian-headless npm; deferred to Phase 3
- **Bidirectional Obsidian sync** — detecting and importing user edits from vault files; deferred
- **Voice mode integration** — audio briefs from KB topics; deferred to Phase 3
- **Full pipeline integration** — making KB compile mandatory in `aca pipeline daily`; this proposal adds it as optional

## Approaches Considered

### Approach A: Monolithic KB Service (Recommended)

**Description**: Single `KnowledgeBaseService` class handles compilation, index generation, and relationship detection. Health checks and Q&A are separate services that consume Topic data.

**Pros**:
- Single service owns the compilation pipeline — clear ownership
- Matches existing pattern (e.g., `SummarizationService` owns summarization end-to-end)
- Transaction boundaries are simple — one service, one DB session per compile run
- Easier to reason about compilation order (gather → match → compile → index)

**Cons**:
- Service grows large as KB complexity increases
- Index generation and relationship detection are conceptually distinct concerns

**Effort**: M

### Approach B: Microservice Decomposition

**Description**: Separate services for each concern: `TopicCompiler`, `TopicMatcher`, `IndexGenerator`, `RelationshipDetector`. Orchestrated by a lightweight `KBPipeline` coordinator.

**Pros**:
- Each service is focused and testable in isolation
- Relationship detection can be swapped (DB-only vs Graphiti) without touching compilation
- Index generation can run independently (e.g., on a schedule)

**Cons**:
- More files, more wiring, more interfaces to maintain
- Orchestration logic adds complexity
- Over-engineered for current scale (~100s of topics, not 100Ks)
- Doesn't match existing project patterns (project favors cohesive services)

**Effort**: L

### Approach C: Event-Driven Compilation

**Description**: Theme extraction publishes events; a KB listener compiles topics reactively. Uses the existing PGQueuer job queue for async compilation.

**Pros**:
- Decoupled — theme analysis doesn't need to know about KB
- Naturally supports background compilation
- Existing queue infrastructure (PGQueuer worker) handles scheduling

**Cons**:
- Adds eventual consistency complexity — KB may lag behind theme analysis
- Debugging async compilation is harder than sync
- Queue worker architecture adds failure modes (dead letters, retries)
- Incremental compilation needs the full context anyway (all evidence, not just the trigger event)

**Effort**: M-L

### Selected Approach

**Approach A: Monolithic KB Service** — selected because it matches existing project patterns, keeps compilation logic cohesive, and is right-sized for the expected scale. Health checks and Q&A are naturally separate services that read Topic data. Index generation is a method on the KB service (not a separate service) since it runs at the end of every compilation cycle.

The graceful-degradation pattern for graph integration (DB-primary, graph-optional) is orthogonal to the service structure and works with any approach.
