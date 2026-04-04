# Tasks: Obsidian Knowledge Base

## Phase 1: Data Model & Foundation

- [ ] 1.1 Write tests for Topic and TopicNote models — CRUD, slug generation, uniqueness, status transitions, self-referential FKs
  **Spec scenarios**: knowledge-base: Topic Data Model (create topic, slug uniqueness, topic note creation)
  **Design decisions**: D2 (DB-primary relationships)
  **Dependencies**: None

- [ ] 1.2 Create Topic, TopicNote, TopicStatus SQLAlchemy models in `src/models/topic.py` — fields per spec, TopicStatus enum, indexes on slug/status/category/trend
  **Dependencies**: 1.1

- [ ] 1.3 Create Alembic migration for topics and topic_notes tables — include PG enum for TopicStatus, indexes, self-referential FKs
  **Dependencies**: 1.2

- [ ] 1.4 Add KB model settings to `settings/models.yaml` — `MODEL_KB_COMPILATION` (default: claude-sonnet-4-5), `MODEL_KB_INDEX` (default: claude-haiku-4-5)
  **Spec scenarios**: knowledge-base: Model Configuration (default model settings, model override)
  **Design decisions**: D7 (model configuration)
  **Dependencies**: None

- [ ] 1.5 Add KB compilation prompts to `settings/prompts.yaml` — topic compilation prompt (evidence → article), relationship detection prompt, index summary prompt
  **Dependencies**: None

## Phase 2: Compilation Service

- [ ] 2.1 Write tests for KnowledgeBaseService — evidence gathering, exact matching, semantic matching, article compilation (mock LLM), relationship detection, index regeneration, incremental vs full, single-topic, no-evidence case, LLM failure handling
  **Spec scenarios**: knowledge-base: KB Compilation Service (all 7 scenarios), Topic Relationship Management (all 3 scenarios)
  **Design decisions**: D1 (monolithic service), D2 (DB-primary graph-optional), D3 (two-phase matching)
  **Dependencies**: 1.2

- [ ] 2.2 Create `src/services/knowledge_base.py` — KnowledgeBaseService with compile(), compile_full(), compile_topic() methods; evidence gathering from ThemeAnalysis/summaries/content; two-phase topic matching; LLM article compilation; relationship detection; graceful graph sync
  **Dependencies**: 2.1, 1.2, 1.4, 1.5

- [ ] 2.3 Write tests for kb_indices table and index generation — master/category/trend/recency index content, regeneration timing
  **Spec scenarios**: knowledge-base: Index Generation (all 4 scenarios)
  **Design decisions**: D4 (cached markdown in DB)
  **Dependencies**: 1.3

- [ ] 2.4 Create kb_indices Alembic migration and add index generation methods to KnowledgeBaseService — generate_indices() called at end of compilation
  **Dependencies**: 2.3, 2.2

## Phase 3: CLI Commands

- [ ] 3.1 Write tests for `aca kb` CLI commands — compile, list, show, index with various flags, JSON output mode, error cases
  **Spec scenarios**: knowledge-base: KB CLI Commands (all 4 scenarios)
  **Dependencies**: 2.2

- [ ] 3.2 Create `src/cli/kb_commands.py` — Typer command group with compile (--full, --topic), list (--category, --trend, --status, --json), show (--json), index (--category) commands
  **Dependencies**: 3.1, 2.2

## Phase 4: API Endpoints

- [ ] 4.1 Write tests for KB API endpoints — CRUD topics, notes, compile trigger, index retrieval, pagination, auth, 404 handling
  **Spec scenarios**: knowledge-base: KB API Endpoints (all 10 scenarios)
  **Design decisions**: D8 (route structure)
  **Dependencies**: 2.2

- [ ] 4.2 Create `src/api/kb_routes.py` — APIRouter at /api/v1/kb/ with GET/POST/PATCH/DELETE topics, notes, compile, index endpoints; mount in app.py
  **Dependencies**: 4.1, 2.2

## Phase 5: MCP Tools

- [ ] 5.1 Write tests for KB MCP tools — search, get_topic, update_topic, add_topic_note, get_kb_index, compile
  **Spec scenarios**: knowledge-base: KB MCP Tools (all 6 scenarios)
  **Dependencies**: 2.2

- [ ] 5.2 Add KB MCP tools to `src/mcp_server.py` — search_knowledge_base, get_topic, update_topic, add_topic_note, get_kb_index, compile_knowledge_base
  **Dependencies**: 5.1, 2.2

## Phase 6: Q&A Mode

- [ ] 6.1 Write tests for KB Q&A service — question answering, file-back mode, no matching topics case
  **Spec scenarios**: knowledge-base: KB Q&A Mode (all 3 scenarios)
  **Design decisions**: D5 (lightweight agent loop)
  **Dependencies**: 2.2

- [ ] 6.2 Create `src/services/kb_qa.py` — KBQAService with query() method; reads master index, identifies topics, reads articles, synthesizes answer; optional file-back as TopicNote
  **Dependencies**: 6.1, 2.2

- [ ] 6.3 Add `aca kb query` CLI command and POST `/api/v1/kb/query` endpoint
  **Dependencies**: 6.2, 3.2, 4.2

## Phase 7: Health Checks

- [ ] 7.1 Write tests for KB health check service — stale detection, merge candidates, coverage gaps, auto-fix, report format
  **Spec scenarios**: knowledge-base: KB Health Checks (all 5 scenarios)
  **Design decisions**: D9 (configurable thresholds)
  **Dependencies**: 2.2

- [ ] 7.2 Create `src/services/kb_health.py` — KBHealthService with lint(), lint_fix() methods; stale detection, merge candidates, coverage gaps, article quality; markdown report output
  **Dependencies**: 7.1, 2.2

- [ ] 7.3 Add `aca kb lint` CLI command (--fix flag) and GET `/api/v1/kb/health` endpoint
  **Dependencies**: 7.2, 3.2, 4.2

## Phase 8: Obsidian Export Extension

- [ ] 8.1 Write tests for Topic export in ObsidianExporter — _overview.md generation, source extracts, 3-tier vault structure, incremental export via article_version, category indices
  **Spec scenarios**: knowledge-base: Obsidian Topic Export (all 4 scenarios)
  **Design decisions**: D6 (vault structure extension)
  **Dependencies**: 2.2

- [ ] 8.2 Extend `src/sync/obsidian_exporter.py` with topic export phase — export _overview.md per topic, source extracts per content item, category index files, update master _index.md; extend frontmatter.py with topic format
  **Dependencies**: 8.1

## Phase 9: Pipeline Integration

- [ ] 9.1 Write test for optional KB compile step in pipeline
  **Spec scenarios**: knowledge-base: Pipeline Integration (both scenarios)
  **Dependencies**: 2.2

- [ ] 9.2 Add optional KB compile step to `src/cli/pipeline_commands.py` — runs after theme analysis, controlled by settings flag (default: disabled)
  **Dependencies**: 9.1, 2.2, 3.2
