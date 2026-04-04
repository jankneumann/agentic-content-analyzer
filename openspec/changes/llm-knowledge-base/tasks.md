# Tasks: LLM Knowledge Base

## Phase 1: Data Model & Configuration

- [ ] 1.1 Write tests for TopicCategory, Topic, and TopicNote models — CRUD, lifecycle transitions, slug generation, category hierarchy, self-referential relationships
  **Spec scenarios**: knowledge-base.1 (topic created from theme), knowledge-base.1 (lifecycle transitions), knowledge-base.1 (hierarchy), knowledge-base.2 (category hierarchy), knowledge-base.2 (category seeding)
  **Contracts**: contracts/db/schema.sql
  **Design decisions**: D2 (full superset + dedicated category table)
  **Dependencies**: None

- [ ] 1.2 Create TopicCategory SQLAlchemy model (`src/models/topic_category.py`) — hierarchical taxonomy with parent_id self-referential FK, slug, name, icon, color, display_order
  **Dependencies**: 1.1

- [ ] 1.3 Create Topic SQLAlchemy model (`src/models/topic.py`) — full superset of ThemeData with TopicStatus enum, category_id FK to TopicCategory, slug generation, all indexes
  **Dependencies**: 1.1, 1.2

- [ ] 1.4 Create TopicNote SQLAlchemy model (`src/models/topic_note.py`) — foreign key to Topic, note_type, author, filed_back
  **Dependencies**: 1.1

- [ ] 1.5 Create Alembic migration for topic_categories, topics, and topic_notes tables — include TopicStatus enum, seed 8 default categories, all indexes, self-referential FKs
  **Dependencies**: 1.2, 1.3, 1.4

- [ ] 1.6 Export new models from `src/models/__init__.py` — TopicCategory, Topic, TopicNote, TopicStatus
  **Dependencies**: 1.2, 1.3, 1.4

- [ ] 1.7 Create `settings/knowledge_base.yaml` — compilation config (thresholds, limits, index types) and add KB prompt templates to `settings/prompts.yaml`
  **Design decisions**: D7 (compilation in pipeline)
  **Dependencies**: None

## Phase 2: KB Compilation Service

- [ ] 2.1 Write tests for KBCompiler — evidence gathering, topic matching (exact + semantic), article compilation, relationship updates, index regeneration
  **Spec scenarios**: knowledge-base.3 (incremental compile), knowledge-base.3 (full recompile), knowledge-base.3 (topic matching), knowledge-base.3 (relationship updates)
  **Design decisions**: D5 (semantic matching), D6 (GraphitiClient abstraction)
  **Dependencies**: 1.2, 1.3

- [ ] 2.2 Create KBCompiler service (`src/services/kb_compiler.py`) — incremental compilation: gather evidence, match topics, LLM article generation, GraphitiClient relationship sync
  **Dependencies**: 2.1, 1.6

- [ ] 2.3 Write tests for KBIndexGenerator — master index, category index, trend index, relationship map generation
  **Spec scenarios**: knowledge-base.4 (master index), knowledge-base.4 (category index), knowledge-base.4 (trend index), knowledge-base.4 (relationship map), knowledge-base.4 (indices readable by agents)
  **Design decisions**: D3 (indices as special Topic records)
  **Dependencies**: 1.2

- [ ] 2.4 Create KBIndexGenerator service (`src/services/kb_index_generator.py`) — generate cached markdown indices as special Topic records with `_` slug prefix
  **Dependencies**: 2.3

## Phase 3: KB Health Check & Linting

- [ ] 3.1 Write tests for KBHealthCheck — stale detection, merge candidates, coverage gaps, auto-fix behavior
  **Spec scenarios**: knowledge-base.7 (stale detection), knowledge-base.7 (merge candidates), knowledge-base.7 (coverage gaps), knowledge-base.7 (health report)
  **Dependencies**: 1.2

- [ ] 3.2 Create KBHealthCheck service (`src/services/kb_health.py`) — health checks with optional auto-fix, markdown report generation
  **Dependencies**: 3.1

## Phase 4: CLI Commands

- [ ] 4.1 Write tests for CLI commands — compile, list, show, index, query, lint subcommands
  **Spec scenarios**: knowledge-base.8 (list with filters), knowledge-base.8 (show article), knowledge-base.8 (show index), knowledge-base.8 (query KB)
  **Dependencies**: 2.2, 2.4, 3.2

- [ ] 4.2 Create CLI command group (`src/cli/kb_commands.py`) — `aca kb compile|list|show|index|query|lint` using Typer, with sync adapters for async services
  **Dependencies**: 4.1

- [ ] 4.3 Register CLI command group in `src/cli/app.py` — `app.add_typer(kb_app, name="kb")`
  **Dependencies**: 4.2

## Phase 5: API Endpoints

- [ ] 5.1 Write tests for API endpoints — CRUD topics, notes, compile trigger, index retrieval, health check
  **Spec scenarios**: knowledge-base.9 (list topics), knowledge-base.9 (get topic detail), knowledge-base.9 (create topic), knowledge-base.9 (get notes), knowledge-base.9 (404 handling)
  **Contracts**: contracts/openapi/v1.yaml
  **Dependencies**: 2.2, 2.4, 3.2

- [ ] 5.2 Create API routes (`src/api/kb_routes.py`) — FastAPI router with all KB endpoints under `/api/v1/kb/`
  **Dependencies**: 5.1

- [ ] 5.3 Register API router in `src/api/app.py` — `app.include_router(kb_router)`
  **Dependencies**: 5.2

## Phase 6: MCP Tools & Agent Integration

- [ ] 6.1 Write tests for MCP tools — search_knowledge_base, get_topic, update_topic, add_topic_note, get_kb_index, compile_knowledge_base
  **Spec scenarios**: knowledge-base.10 (search returns topics), knowledge-base.10 (get_topic returns article), knowledge-base.10 (add_topic_note), knowledge-base.10 (compile triggers)
  **Dependencies**: 2.2, 2.4

- [ ] 6.2 Add MCP tools to `src/mcp_server.py` — 6 `@mcp.tool()` functions for KB access
  **Dependencies**: 6.1

- [ ] 6.3 Write tests for KnowledgeBase specialist agent — index navigation, article reading, answer synthesis, file-back behavior
  **Spec scenarios**: knowledge-base.6 (agent answers using topics), knowledge-base.6 (agent files answer back), knowledge-base.6 (Research specialist has KB tools)
  **Design decisions**: D4 (new specialist + KB tools on Research)
  **Dependencies**: 6.2

- [ ] 6.4 Create KnowledgeBase specialist agent (`src/agents/specialists/knowledge_base.py`) — tool definitions, navigation prompt, answer synthesis
  **Dependencies**: 6.3

- [ ] 6.5 Add KB tools to Research specialist (`src/agents/specialists/research.py`) — search_knowledge_base, get_topic, get_kb_index tool definitions
  **Dependencies**: 6.2

## Phase 7: Pipeline Integration

- [ ] 7.1 Write tests for pipeline integration — KB compile step runs after theme analysis, --skip-kb flag works
  **Spec scenarios**: knowledge-base.5 (pipeline includes KB compilation), knowledge-base.5 (pipeline KB step skippable), knowledge-base.5 (on-demand compilation via API)
  **Design decisions**: D7 (compilation in pipeline with skip option)
  **Dependencies**: 2.2, 4.2

- [ ] 7.2 Integrate KB compilation into pipeline runner — add step after theme analysis, add --skip-kb flag
  **Dependencies**: 7.1

## Phase 8: Graph Backend Abstraction Compliance

- [ ] 8.1 Write tests verifying GraphitiClient-only access — no direct Cypher/FalkorDB/Neo4j queries in KB services
  **Spec scenarios**: knowledge-base.11 (relationships via GraphitiClient), knowledge-base.11 (context via GraphitiClient)
  **Design decisions**: D6 (graph backend abstraction)
  **Dependencies**: 2.2, 6.4

- [ ] 8.2 Review and validate all KB services use GraphitiClient abstraction — audit imports, remove any direct graph DB access
  **Dependencies**: 8.1

## Phase 9: Obsidian Export

- [ ] 9.1 Write tests for Obsidian export service — folder structure from category hierarchy, YAML frontmatter, wikilinks, index files, ZIP generation, incremental export
  **Spec scenarios**: knowledge-base.12 (category folder structure), knowledge-base.12 (YAML frontmatter), knowledge-base.12 (wikilinks), knowledge-base.12 (index files), knowledge-base.12 (ZIP via API), knowledge-base.12 (incremental export)
  **Design decisions**: D8 (category hierarchy as folder structure)
  **Dependencies**: 1.2, 1.3, 2.4

- [ ] 9.2 Create Obsidian export service (`src/services/kb_obsidian_export.py`) — generate vault directory with category-based folders, topic .md files with frontmatter, wikilinks, and index files
  **Dependencies**: 9.1

- [ ] 9.3 Add `aca kb export` CLI command and `GET /api/v1/kb/export/obsidian` API endpoint
  **Dependencies**: 9.2, 4.2, 5.2

- [ ] 9.4 Add category CRUD API endpoints (`/api/v1/kb/categories`) — list tree, create subcategory
  **Spec scenarios**: knowledge-base.2 (subcategory created via API), knowledge-base.2 (category listing)
  **Dependencies**: 1.2, 5.2

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1 | 1.1 - 1.7 | Data model, migration, settings |
| 2 | 2.1 - 2.4 | Compilation + index generation |
| 3 | 3.1 - 3.2 | Health checks + linting |
| 4 | 4.1 - 4.3 | CLI commands |
| 5 | 5.1 - 5.3 | API endpoints |
| 6 | 6.1 - 6.5 | MCP tools + agent |
| 7 | 7.1 - 7.2 | Pipeline integration |
| 8 | 8.1 - 8.2 | Graph abstraction compliance |
| 9 | 9.1 - 9.4 | Obsidian export + category CRUD |
