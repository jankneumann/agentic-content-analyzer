# Change Context: obsidian-knowledge-base

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Test(s) | Contract Ref | Design Decision | Files Changed | Evidence |
|--------|-------------|-------------|---------|--------------|-----------------|---------------|----------|
| kb.1 | specs/knowledge-base/spec.md | Topic + TopicNote SQLAlchemy models, slug uniqueness, status enum | `test_topic_models.py::test_topic_create`, `::test_slug_uniqueness`, `::test_topic_note_create`, `::test_archived_excluded` | --- | D2 | `src/models/topic.py`, `alembic/versions/c5f6a7b8d9e0_add_topic_tables.py` | TBD |
| kb.2 | specs/knowledge-base/spec.md | KB compilation: incremental, full, single-topic, exact + semantic matching, LLM article | `test_knowledge_base.py::test_compile_incremental`, `::test_compile_full`, `::test_compile_topic`, `::test_semantic_match`, `::test_embedding_failure_fallback`, `::test_first_compilation`, `::test_no_evidence`, `::test_llm_failure_skips_topic` | --- | D1, D3 | `src/services/knowledge_base.py` | TBD |
| kb.3 | specs/knowledge-base/spec.md | Compilation concurrency: pg_advisory_lock, release on completion, stale lock recovery | `test_knowledge_base.py::test_concurrent_compile_rejected`, `::test_lock_released_on_failure`, `::test_stale_lock_recovery` | --- | D10 | `src/services/knowledge_base.py` | TBD |
| kb.4 | specs/knowledge-base/spec.md | Topic relationships: DB-primary (related_topic_ids JSON, parent_topic_id FK), graph-optional | `test_knowledge_base.py::test_db_relationships`, `::test_graph_sync_failure_continues` | --- | D2 | `src/services/knowledge_base.py`, `src/models/topic.py` | TBD |
| kb.5 | specs/knowledge-base/spec.md | Topic merge detection: cosine > 0.90, exclude empty articles | `test_knowledge_base.py::test_merge_candidate_detected`, `::test_empty_article_excluded_from_merge` | --- | D3 | `src/services/knowledge_base.py` | TBD |
| kb.6 | specs/knowledge-base/spec.md | Index generation: master, category, trend, recency; cached markdown; empty-KB; active-only | `test_kb_index.py::test_master_index`, `::test_category_index`, `::test_trend_index`, `::test_recency_index`, `::test_empty_kb_index` | --- | D4 | `src/services/knowledge_base.py` | TBD |
| kb.7 | specs/knowledge-base/spec.md | KB CLI commands: list, show, index, compile (full/topic) | `test_kb_commands.py::test_list_topics`, `::test_show_topic`, `::test_show_index`, `::test_compile_via_cli` | --- | --- | `src/cli/kb_commands.py`, `src/cli/app.py` | TBD |
| kb.8 | specs/knowledge-base/spec.md | KB API: list/get/create/update/archive topics, notes CRUD, compile (incl. 409), index | `test_kb_routes.py::test_list_topics`, `::test_get_topic`, `::test_get_404`, `::test_create_topic`, `::test_update_topic`, `::test_archive_topic`, `::test_notes_crud`, `::test_compile_endpoint`, `::test_compile_409`, `::test_index_endpoint` | --- | D8 | `src/api/kb_routes.py`, `src/api/app.py` | TBD |
| kb.9 | specs/knowledge-base/spec.md | KB MCP tools: search, get_topic, update_topic, add_topic_note, get_kb_index, compile | `test_mcp_kb.py::test_search_kb`, `::test_get_topic_tool`, `::test_update_topic_tool`, `::test_add_topic_note_tool`, `::test_get_kb_index_tool`, `::test_compile_tool` | --- | --- | `src/mcp_server.py` | TBD |
| kb.10 | specs/knowledge-base/spec.md | KB Q&A: question answering, file-back, no matches, LLM failure, top-10 truncation | `test_kb_qa.py::test_query`, `::test_file_back`, `::test_no_matches`, `::test_llm_failure`, `::test_top_10_truncation` | --- | D5 | `src/services/kb_qa.py`, `src/cli/kb_commands.py`, `src/api/kb_routes.py` | TBD |
| kb.11 | specs/knowledge-base/spec.md | KB Health: stale, merge candidates, coverage gaps, auto-fix, markdown report | `test_kb_health.py::test_stale_detection`, `::test_merge_candidates`, `::test_coverage_gaps`, `::test_auto_fix_stale`, `::test_report_format` | --- | D9 | `src/services/kb_health.py`, `src/cli/kb_commands.py`, `src/api/kb_routes.py` | TBD |
| kb.12 | specs/knowledge-base/spec.md | Obsidian topic export: 3-tier vault, _overview.md, source extracts, incremental | `test_obsidian_topic_export.py::test_topic_overview`, `::test_source_extract`, `::test_incremental`, `::test_three_tier_structure` | --- | D6 | `src/sync/obsidian_exporter.py`, `src/sync/obsidian_frontmatter.py` | TBD |
| kb.13 | specs/knowledge-base/spec.md | Model configuration: MODEL_KB_COMPILATION + MODEL_KB_INDEX defaults + override | `test_kb_models_config.py::test_default_kb_models`, `::test_kb_model_override` | --- | D7 | `src/config/models.py`, `settings/models.yaml`, `settings/prompts.yaml` | TBD |
| kb.14 | specs/knowledge-base/spec.md | Optional pipeline integration: KB step after theme analysis, default disabled | `test_pipeline_kb.py::test_kb_step_enabled`, `::test_kb_step_disabled` | --- | --- | `src/cli/pipeline_commands.py`, `src/config/settings.py` | TBD |

## Design Decision Trace

| Decision | Rationale | Implementation |
|----------|-----------|----------------|
| D1: Monolithic KnowledgeBaseService | Matches existing project patterns; right-sized for ~100s of topics; cohesive compilation pipeline | `src/services/knowledge_base.py` — single class with `compile()`, `compile_full()`, `compile_topic()` methods |
| D2: DB-primary, graph-optional relationships | Graph backend may be unavailable in some deployments; same graceful-degradation as ObsidianExporter for Neo4j entities | `Topic.related_topic_ids` JSON, `Topic.parent_topic_id` FK; `_sync_to_graph()` wrapped in try/except |
| D3: Two-phase topic matching (exact then embedding) | LLM matching too expensive/slow; keyword/TF-IDF too weak for semantic similarity (e.g., "RAG" vs "Retrieval-Augmented Generation") | `KnowledgeBaseService._match_to_topic()` — exact name match first, then cosine > 0.85 |
| D4: Cached markdown indices in DB | Dynamic regeneration too expensive for hundreds of topics; file-based not API/MCP accessible | `kb_indices` table (index_type, content, generated_at); regenerated at end of each compile cycle |
| D5: Lightweight Q&A agent loop | Full agent framework overkill; topic articles are already compiled summaries (better than RAG-over-articles) | `KBQAService.query()` — read master index → identify topics → read articles → synthesize answer |
| D6: Obsidian vault structure extension | Coexists with existing flat exports; 3-tier (Category/Topic/Source) is additive | `ObsidianExporter.export_topics()` new method; existing export phases unchanged |
| D7: MODEL_KB_COMPILATION + MODEL_KB_INDEX | Follow existing `MODEL_*` pattern; compilation needs capable model, indexing simpler | `ModelStep.KB_COMPILATION`, `ModelStep.KB_INDEX` enum values + YAML defaults |
| D8: APIRouter with auth dependency at /api/v1/kb/ | Consistent with existing API pattern; shared auth middleware | `kb_router = APIRouter(prefix="/api/v1/kb", dependencies=[Depends(verify_admin_key)])` |
| D9: Configurable health check thresholds | Different deployments have different content volumes/freshness expectations | `KB_STALE_THRESHOLD_DAYS`, `KB_MERGE_SIMILARITY_THRESHOLD`, `KB_MIN_TOPICS_PER_CATEGORY` settings |
| D10: pg_advisory_lock for compilation concurrency | Application-level lock fails across processes; queue-based overkill; advisory locks work in any deployment | `pg_try_advisory_lock(hashint('kb_compile'))`; stale lock recovery via timeout setting |

## Coverage Summary

- **Requirements traced**: 14
- **Tests mapped**: TBD (Phase 2 GREEN)
- **Evidence collected**: 0/14
- **Gaps**: 0
- **Deferred**: Voice mode integration, Obsidian Mode 1/3, bidirectional sync (per proposal Non-Goals)
