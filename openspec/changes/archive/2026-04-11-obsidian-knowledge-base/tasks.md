# Tasks: Obsidian Knowledge Base

## Phase 1: Data Model & Foundation

- [x] 1.1 Write tests for Topic and TopicNote models — CRUD, slug generation, uniqueness, status transitions, self-referential FKs, embedding column, archived topic exclusion from indices
  **Spec scenarios**: knowledge-base: Topic Data Model (create topic, slug uniqueness, topic note creation)
  **Design decisions**: D2 (DB-primary relationships)
  **Dependencies**: None

- [x] 1.2 Create Topic, TopicNote, TopicStatus SQLAlchemy models in `src/models/topic.py` — fields per spec including embedding vector column, TopicStatus enum, indexes on slug/status/category/trend
  **Dependencies**: 1.1

- [x] 1.3 Create Alembic migration for topics, topic_notes, and kb_indices tables — include PG enum for TopicStatus, indexes, self-referential FKs, vector column for embedding
  **Dependencies**: 1.2

- [x] 1.4 Add KB model settings to `settings/models.yaml` — `MODEL_KB_COMPILATION` (default: claude-sonnet-4-5), `MODEL_KB_INDEX` (default: claude-haiku-4-5)
  **Spec scenarios**: knowledge-base: Model Configuration (default model settings, model override)
  **Design decisions**: D7 (model configuration)
  **Dependencies**: None

- [x] 1.5 Add KB compilation prompts to `settings/prompts.yaml` — topic compilation prompt (evidence -> article), relationship detection prompt, index summary prompt
  **Dependencies**: None

## Phase 2: Compilation Service

- [x] 2.1 Write tests for KnowledgeBaseService — evidence gathering, exact matching, semantic matching (including embedding failure fallback), first compilation (no prior state), article compilation (mock LLM), relationship detection, concurrency lock, incremental vs full, single-topic, no-evidence case, LLM failure handling, merge detection with empty articles
  **Spec scenarios**: knowledge-base: KB Compilation Service (all scenarios), Compilation Concurrency (all 3 scenarios), Topic Relationship Management (all 3 scenarios)
  **Design decisions**: D1 (monolithic service), D2 (DB-primary graph-optional), D3 (two-phase matching), D10 (advisory lock concurrency)
  **Dependencies**: 1.2

- [x] 2.2 Create `src/services/knowledge_base.py` — KnowledgeBaseService with compile(), compile_full(), compile_topic() methods; pg_advisory_lock for concurrency; evidence gathering from ThemeAnalysis/summaries/content; two-phase topic matching (exact + embedding with fallback); topic embedding generation; LLM article compilation; relationship detection; graceful graph sync; compilation_model recording
  **Dependencies**: 2.1, 1.3, 1.4, 1.5

- [x] 2.3 Write tests for index generation — master/category/trend/recency index content, empty-KB case, regeneration timing, active-only filtering
  **Spec scenarios**: knowledge-base: Index Generation (all 7 scenarios including empty KB, trend, recency)
  **Design decisions**: D4 (cached markdown in DB)
  **Dependencies**: 1.3, 2.2

- [x] 2.4 Add index generation methods to KnowledgeBaseService — generate_indices() called at end of compilation; writes to kb_indices table
  **Dependencies**: 2.3, 2.2

## Phase 3: CLI Commands

- [x] 3.1 Write tests for `aca kb` CLI commands — compile (including concurrency rejection), list, show, index with various flags, JSON output mode, error cases
  **Spec scenarios**: knowledge-base: KB CLI Commands (all 4 scenarios)
  **Dependencies**: 2.2

- [x] 3.2 Create `src/cli/kb_commands.py` — Typer command group with compile (--full, --topic), list (--category, --trend, --status, --json), show (--json), index (--category) commands
  **Dependencies**: 3.1, 2.2

## Phase 4: API Endpoints

- [x] 4.1 Write tests for KB API topic CRUD — create, get, list (pagination), update, archive, 404 handling, auth
  **Spec scenarios**: knowledge-base: KB API Endpoints (list, get, get not found, create, update, archive)
  **Design decisions**: D8 (route structure)
  **Dependencies**: 2.2

- [x] 4.2 Write tests for KB API operations — notes CRUD, compile trigger (including 409 conflict), index retrieval
  **Spec scenarios**: knowledge-base: KB API Endpoints (notes, compile, compile conflict, index)
  **Dependencies**: 2.2

- [x] 4.3 Create `src/api/kb_routes.py` — APIRouter at /api/v1/kb/ with all endpoints; mount in app.py
  **Dependencies**: 4.1, 4.2, 2.2

## Phase 5: MCP Tools

- [x] 5.1 Write tests for KB MCP tools — search, get_topic, update_topic, add_topic_note, get_kb_index, compile
  **Spec scenarios**: knowledge-base: KB MCP Tools (all 6 scenarios)
  **Dependencies**: 2.2

- [x] 5.2 Add KB MCP tools to `src/mcp_server.py` — search_knowledge_base, get_topic, update_topic, add_topic_note, get_kb_index, compile_knowledge_base
  **Dependencies**: 5.1, 2.2

## Phase 6: Q&A Mode

- [x] 6.1 Write tests for KB Q&A service — question answering, file-back mode, no matching topics, LLM failure, topic truncation (>10 topics)
  **Spec scenarios**: knowledge-base: KB Q&A Mode (all 6 scenarios including failure and truncation)
  **Design decisions**: D5 (lightweight agent loop)
  **Dependencies**: 2.2

- [x] 6.2 Create `src/services/kb_qa.py` — KBQAService with query() method; reads master index, identifies topics (top 10 by relevance), reads articles + relationships, synthesizes answer; optional file-back as TopicNote
  **Dependencies**: 6.1, 2.2

- [x] 6.3 Add `aca kb query` CLI command to `src/cli/kb_commands.py` — query with --file-back flag, JSON output
  **Dependencies**: 6.2, 3.2

- [x] 6.4 Add POST `/api/v1/kb/query` endpoint to `src/api/kb_routes.py`
  **Dependencies**: 6.2, 4.3

## Phase 7: Health Checks

- [x] 7.1 Write tests for KB health check service — stale detection, merge candidates, coverage gaps, article quality scoring, auto-fix, report format
  **Spec scenarios**: knowledge-base: KB Health Checks (all 5 scenarios)
  **Design decisions**: D9 (configurable thresholds, quality scoring)
  **Dependencies**: 2.2

- [x] 7.2 Create `src/services/kb_health.py` — KBHealthService with lint(), lint_fix() methods; stale detection, merge candidates, coverage gaps, article quality (evidence count, recency, completeness); markdown report output
  **Dependencies**: 7.1, 2.2

- [x] 7.3 Add `aca kb lint` CLI command (--fix flag) to `src/cli/kb_commands.py`
  **Dependencies**: 7.2, 3.2

- [x] 7.4 Add GET `/api/v1/kb/health` endpoint to `src/api/kb_routes.py`
  **Dependencies**: 7.2, 4.3

## Phase 8: Obsidian Export Extension

- [x] 8.1 Write tests for Topic export in ObsidianExporter — _overview.md generation with wikilinks (`[[../../Category/Topic/_overview|Name]]`), source extracts, 3-tier vault structure, incremental export via article_version, category indices
  **Spec scenarios**: knowledge-base: Obsidian Topic Export (all 4 scenarios)
  **Design decisions**: D6 (vault structure extension)
  **Dependencies**: 2.2

- [x] 8.2 Extend `src/sync/obsidian_exporter.py` with topic export phase — export _overview.md per topic, source extracts per content item, category index files, update master _index.md
  **Dependencies**: 8.1

- [x] 8.3 Extend `src/sync/obsidian_frontmatter.py` with topic frontmatter format
  **Dependencies**: 8.1

## Phase 9: Pipeline Integration

- [x] 9.1 Write test for optional KB compile step in pipeline
  **Spec scenarios**: knowledge-base: Pipeline Integration (both scenarios)
  **Dependencies**: 2.2

- [x] 9.2 Add optional KB compile step to `src/cli/pipeline_commands.py` — runs after theme analysis, controlled by settings flag (default: disabled)
  **Dependencies**: 9.1, 2.2, 3.2
