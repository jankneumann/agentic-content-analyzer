---

## Phase: Plan (2026-04-04)

**Agent**: Claude Opus 4.6 | **Session**: session_017e4kzPvD1eT7x5mNDjanjy

### Decisions
1. **Database-first architecture** — PostgreSQL `topics` table is the canonical representation; Obsidian is a derived export/interface layer. Enables existing hybrid search, SQL queryability, multi-user access, and natural integration with pipeline/agents/API.
2. **Topic as full ThemeData superset** — All ThemeData fields promoted to individual DB columns (not JSONB blob) for direct SQL filtering and indexing.
3. **Indices as special Topic records** — Auto-maintained index files stored as Topic records with `_` slug prefix. Same read path as regular topics; no special API needed.
4. **New KB specialist + KB tools on Research agent** — Dedicated KnowledgeBase specialist for Q&A with topic-centric navigation. KB tools also exposed to Research specialist for cross-cutting queries.
5. **Pipeline integration with skip option** — KB compilation runs automatically after theme analysis in daily pipeline, with `--skip-kb` flag for opt-out.
6. **Graph backend abstraction** — All topic relationship operations through GraphitiClient only, supporting both Neo4j and FalkorDB backends.

### Alternatives Considered
- Flat markdown files (Karpathy's approach): rejected because it disconnects from existing infrastructure, doesn't scale past ~1000 topics, and lacks semantic search/typed relationships
- Hybrid DB+filesystem: rejected due to bidirectional sync complexity and conflict resolution challenges
- Extending Research specialist only (no new KB specialist): rejected to maintain clean separation of concerns
- Lean Topic model with JSONB overflow: rejected because direct column storage enables SQL-level filtering and proper indexes

### Trade-offs
- Accepted higher model complexity (full superset) over simpler model (lean+links) because query performance and schema clarity outweigh migration cost
- Accepted Obsidian as derived view (not source of truth) over native Obsidian because database scalability and integration matter more than zero-friction file editing
- Accepted pipeline latency (~30-60s) over on-demand-only compilation because topic freshness is more valuable than pipeline speed

### Open Questions
- [ ] How should the Obsidian export format handle topic hierarchies (nested folders vs flat with frontmatter)?
- [ ] Should the KB compilation use a dedicated LLM model or share the existing theme analysis model?
- [ ] Integration with the voice mode mini-KB generation (focused KB for a run pattern)
- [ ] Frontend UI for KB browsing — separate change or integrated into existing web UI?

### Context
Planning session for the LLM Knowledge Base feature, inspired by the personal knowledge base approach. The goal was to design a system that promotes topics/concepts to first-class entities with incremental LLM compilation, auto-maintained indices, Q&A capabilities, and health checks. Selected database-first approach with 8 work packages for local-parallel execution.
