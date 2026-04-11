# Design: Obsidian Knowledge Base

## D1: Monolithic KnowledgeBaseService

**Decision**: Single `KnowledgeBaseService` class owns the compilation pipeline (gather → match → compile → index). Health checks and Q&A are separate services.

**Alternatives considered**:
- Microservice decomposition (TopicCompiler + TopicMatcher + IndexGenerator): Rejected — over-engineered for expected scale (~100s of topics). More wiring, more interfaces, doesn't match existing project patterns.
- Event-driven via PGQueuer: Rejected — adds eventual consistency complexity. Compilation needs full evidence context, not just the trigger event.

**Trade-offs**: Service may grow large over time. Mitigation: extract methods into private helpers; the service is a coordinator, not a monolith of logic.

## D2: DB-Primary, Graph-Optional Relationships

**Decision**: `related_topic_ids` (JSON column) and `parent_topic_id` (FK) are the canonical relationship store. Optional Graphiti sync when graph backend is available.

**Pattern**: Same graceful-degradation pattern used by `ObsidianExporter` for Neo4j entities — try graph, log warning on failure, continue with DB-only data.

**Implementation**:
```python
async def _sync_to_graph(self, topic: Topic, related: list[Topic]) -> None:
    try:
        client = get_graphiti_client()
        # Sync via Graphiti episode API
    except Exception as e:
        logger.warning("Graph sync failed for topic %s: %s", topic.slug, e)
        # DB relationships are already stored — no data loss
```

**Alternatives considered**:
- Graphiti-first: Rejected — adds hard Neo4j/FalkorDB dependency for compilation. Graph backend may not be available in all deployments.
- DB-only (no graph): Rejected — loses rich typed/weighted/temporal relationships when graph IS available.

## D3: Topic Matching Strategy

**Decision**: Two-phase matching: exact name match first, then semantic similarity via embedding cosine distance.

**Threshold**: Cosine similarity > 0.85 for match, > 0.90 for merge candidate flagging.

**Implementation**: Reuse existing `DocumentChunk.embedding` infrastructure — generate topic name + summary embeddings using the same embedding provider. Store in a `topic_embedding` column (vector type, same as chunks).

**Alternatives considered**:
- LLM-based matching (ask LLM if themes are the same topic): Rejected — expensive per-theme, slower, non-deterministic.
- Keyword/TF-IDF matching: Rejected — insufficient for semantic similarity (e.g., "RAG" vs "Retrieval-Augmented Generation").

## D4: Index Storage

**Decision**: Cached markdown stored in a `kb_indices` table (key: index_type, value: markdown text, generated_at: timestamp). Regenerated at the end of each compilation cycle.

**Alternatives considered**:
- File-based indices (write to disk): Rejected — not accessible via API/MCP without additional serving logic.
- Dynamic-only (generate on each request): Rejected — expensive for master index with hundreds of topics.

**Table schema**:
```sql
CREATE TABLE kb_indices (
    id SERIAL PRIMARY KEY,
    index_type VARCHAR(50) UNIQUE NOT NULL,  -- 'master', 'category_ml_ai', 'trend_emerging', 'recency'
    content TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## D5: Q&A Agent Architecture

**Decision**: KB Q&A uses a lightweight agent loop: (1) read master index, (2) identify relevant topics, (3) read topic articles, (4) synthesize answer. Uses the existing LLM provider infrastructure, not a separate agent framework.

**File-back**: Answers optionally filed as TopicNotes. The next compilation cycle can incorporate notes into the topic article.

**Alternatives considered**:
- Full agent specialist (ACA agent framework): Rejected — overkill for a focused Q&A use case. The agent framework is for multi-step analysis tasks.
- RAG over topic articles: Rejected — topic articles are already compiled summaries; reading them directly is more effective than chunking and retrieving.

## D6: Obsidian Vault Structure Extension

**Decision**: Extend the existing exporter with a new export phase for Topics. The 3-tier structure (Category/Topic/Source) is additional to the existing flat export of digests/summaries.

**Implementation order**:
1. Export topic `_overview.md` files (article + frontmatter + wikilinks)
2. Export source extracts (content items linked to topics)
3. Generate category index files at each category folder
4. Update master `_index.md` to include topic counts per category

**Coexistence**: Existing digest/summary/insight exports continue unchanged. Topic exports add new directories alongside existing ones.

## D7: Model Configuration

**Decision**: Follow existing `MODEL_*` pattern. Two new settings:

```yaml
# settings/models.yaml
kb_compilation:
  default: claude-sonnet-4-5
  env_var: MODEL_KB_COMPILATION
  description: Model for compiling topic articles from evidence

kb_index:
  default: claude-haiku-4-5
  env_var: MODEL_KB_INDEX
  description: Model for generating index summaries
```

**Rationale**: Compilation needs a capable model (article synthesis from multiple sources). Index generation is simpler (summary extraction), so a faster/cheaper model suffices.

## D8: API Route Structure

**Decision**: Mount KB routes at `/api/v1/kb/` using a dedicated `APIRouter` with auth dependency.

```python
kb_router = APIRouter(
    prefix="/api/v1/kb",
    tags=["knowledge-base"],
    dependencies=[Depends(verify_admin_key)],
)
```

**Pagination**: Use existing offset/limit pattern from content API. Default limit=50, max limit=200.

## D9: Health Check Thresholds

**Decision**: Configurable thresholds with sensible defaults:

| Check | Default | Setting |
|-------|---------|---------|
| Stale detection | 30 days | `KB_STALE_THRESHOLD_DAYS` |
| Merge similarity | 0.90 | `KB_MERGE_SIMILARITY_THRESHOLD` |
| Coverage minimum | 3 topics/category | `KB_MIN_TOPICS_PER_CATEGORY` |

**Article quality scoring**: The health check evaluates articles on evidence count (number of source items), recency (age of most recent evidence), and completeness (article length relative to evidence volume). Quality scores are informational — they guide recompilation priority, not automatic changes.

**Alternatives considered**:
- Hardcoded thresholds: Rejected — different deployments may have different content volumes and freshness expectations.

## D10: Compilation Concurrency Control

**Decision**: Use a database-level advisory lock (`pg_advisory_lock`) to prevent concurrent compilations. The lock is acquired at the start of compilation and released on completion (success or failure).

**Stale lock recovery**: If a compilation holds the lock for >30 minutes (configurable via `KB_COMPILE_LOCK_TIMEOUT_MINUTES`), the lock is considered stale. The next compilation attempt acquires a new lock.

**Implementation**: Advisory lock key derived from a fixed integer (e.g., `hashint('kb_compile')`). `pg_try_advisory_lock` returns false if already held — no blocking, immediate rejection.

**Alternatives considered**:
- Application-level lock (in-memory flag): Rejected — doesn't work across multiple API processes/workers.
- File-based lock: Rejected — not available in containerized/serverless environments.
- Queue-based (enqueue and process serially): Rejected — overkill for a single-operation lock.
