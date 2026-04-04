# Design: LLM Knowledge Base

## Architecture Overview

```
                          ┌─────────────────────────────┐
                          │     Existing Pipeline        │
                          │  ingest → summarize → theme  │
                          └──────────────┬──────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────────┐
                          │     KB Compilation Service    │
                          │  (incremental or full)        │
                          │                              │
                          │  1. Gather new evidence      │
                          │  2. Match → existing topics  │
                          │  3. LLM compile articles     │
                          │  4. Update relationships     │
                          │  5. Regenerate indices       │
                          └──────┬───────┬───────┬──────┘
                                 │       │       │
                    ┌────────────┘       │       └────────────┐
                    ▼                    ▼                    ▼
           ┌────────────┐     ┌──────────────┐     ┌─────────────┐
           │ PostgreSQL  │     │ GraphitiClient│     │ Index Cache │
           │ topics +    │     │ (Neo4j or     │     │ (special    │
           │ topic_notes │     │  FalkorDB)    │     │  Topic recs)│
           └──────┬─────┘     └──────────────┘     └──────┬──────┘
                  │                                        │
                  └────────────┬───────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌──────────┐   ┌───────────┐   ┌────────────┐
        │ API      │   │ CLI       │   │ MCP Tools  │
        │ /kb/*    │   │ aca kb *  │   │ 6 tools    │
        └──────────┘   └───────────┘   └────────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌──────────┐   ┌───────────┐   ┌────────────┐
        │ Web UI   │   │ Obsidian  │   │ LLM Agents │
        │ (future) │   │ Export    │   │ KB + Rsch  │
        └──────────┘   └───────────┘   └────────────┘
```

## Design Decisions

### D1: Database as Source of Truth (not Markdown Files)

**Decision**: PostgreSQL `topics` table is the canonical representation. Obsidian is a derived export.

**Rationale**: The system already has hybrid search (BM25 + pgvector), tree index chunking, SQLAlchemy models, and a graph-abstracted knowledge graph. Storing topics as DB records enables:
- Structured queries without reading every file
- Semantic search via existing embeddings infrastructure
- Multi-user access with permissions
- Natural integration with pipeline, agents, API
- Scalability beyond 1000+ topics

**Trade-off**: Obsidian users cannot directly edit topics — they must go through MCP tools or CLI import. This is acceptable because the LLM is the primary author of KB content (per Karpathy's design principle: "you rarely ever write or edit the wiki manually, it's the domain of the LLM").

**Alternative rejected**: Flat markdown files (Approach 2). While simpler for personal use, it disconnects from the existing infrastructure and doesn't scale. Bidirectional sync (Approach 3) was rejected due to conflict resolution complexity.

### D2: Topic Model as Full Superset of ThemeData

**Decision**: The `Topic` SQLAlchemy model includes ALL fields from the `ThemeData` Pydantic model as individual database columns, not as a JSONB blob.

**Rationale**: Direct column storage enables:
- SQL-level filtering: `WHERE category = 'ml_ai' AND trend = 'emerging' AND relevance_score > 0.7`
- Database indexes on frequently queried fields
- No JSON path queries or post-fetch filtering
- Clear schema evolution via Alembic migrations

**Fields promoted from ThemeData**:
| ThemeData field | Topic column | Type |
|----------------|-------------|------|
| name | name | String(500) |
| description | summary | Text |
| category | category | Enum(ThemeCategory) |
| trend | trend | Enum(ThemeTrend) |
| relevance_score | relevance_score | Float |
| strategic_relevance | strategic_relevance | Float |
| tactical_relevance | tactical_relevance | Float |
| novelty_score | novelty_score | Float |
| cross_functional_impact | cross_functional_impact | Float |
| mention_count | mention_count | Integer |
| content_ids | source_content_ids | JSON |
| related_themes | related_topic_ids | JSON |
| key_points | key_points | JSON |
| first_seen | first_evidence_at | DateTime |
| last_seen | last_evidence_at | DateTime |

**New fields not in ThemeData**:
| Field | Type | Purpose |
|-------|------|---------|
| slug | String(200), unique | URL-safe identifier |
| status | Enum(TopicStatus) | Lifecycle state |
| article_md | Text | LLM-compiled article |
| article_version | Integer | Version counter |
| parent_topic_id | FK → Topic | Hierarchy |
| merged_into_id | FK → Topic | Merge tracking |
| last_compiled_at | DateTime | Last compilation time |
| compilation_model | String(100) | Which LLM compiled |
| compilation_token_usage | Integer | Token cost |

### D3: Indices as Special Topic Records

**Decision**: Auto-maintained indices are stored as `Topic` records with slugs prefixed by `_` (e.g., `_index`, `_by_category`).

**Rationale**:
- Same read path as regular topics — no special API or model needed
- LLM agents access indices via `get_topic("_index")` — zero new tooling
- Obsidian export includes indices as regular `.md` files
- Cache invalidation is simple: rewrite the record on each compilation

**Index records use**:
- `status = active` (always)
- `category = OTHER`
- `article_md` = the generated index content
- `article_version` incremented on each regeneration
- Other fields (scores, etc.) set to defaults — they're not meaningful for indices

### D4: KB Specialist Agent + KB Tools on Research Agent

**Decision**: Create a new KnowledgeBase specialist agent for dedicated Q&A. Also expose KB tools (`search_knowledge_base`, `get_topic`, `get_kb_index`) to the existing Research specialist.

**Rationale**: The KB specialist has a focused prompt that instructs it to navigate via indices (read `_index` → identify topics → read articles → synthesize). The Research specialist gets KB tools as supplementary — it already has `search_content` and `query_knowledge_graph`, and KB tools add another knowledge source.

**KB specialist tools**:
| Tool | Description |
|------|-------------|
| get_topic | Read a topic article by slug |
| search_knowledge_base | Hybrid search across topics |
| get_kb_index | Read a cached index |
| add_topic_note | File an observation back |
| query_knowledge_graph | Existing Graphiti search |

**Research specialist additional tools** (added to existing set):
| Tool | Description |
|------|-------------|
| search_knowledge_base | Search compiled topics |
| get_topic | Read a topic article |
| get_kb_index | Read KB index |

### D5: Incremental Compilation with Semantic Matching

**Decision**: The compiler uses a two-phase matching strategy: exact name match first, then embedding similarity for fuzzy matching.

**Rationale**: Theme names from different `ThemeAnalysis` runs may vary slightly ("RAG Architectures" vs "RAG Architecture" vs "Retrieval-Augmented Generation"). Exact match handles the common case efficiently; embedding similarity catches variations without false positives.

**Matching pipeline**:
```
Theme name from ThemeAnalysis
  │
  ├─ Exact match against Topic.name → UPDATE existing topic
  │
  ├─ Embedding similarity > 0.85 → UPDATE matched topic
  │   (uses existing embedding infrastructure)
  │
  └─ No match → CREATE new Topic with status=draft
```

**Merge detection** (health check, not compilation):
- Pairwise similarity > 0.90 between existing topics → reported as merge candidates
- Auto-merge with `--fix`: lower mention_count topic merged into higher

### D6: Graph Backend Abstraction

**Decision**: All topic relationship operations use `GraphitiClient` methods exclusively. No direct Cypher, FalkorDB, or Neo4j-specific queries.

**Rationale**: The parallel FalkorDB migration effort is abstracting the graph backend behind Graphiti. Topic relationships must be stored portably to work with both backends.

**Operations through GraphitiClient**:
- `add_episode()` — store topic compilation as episodes (for entity extraction)
- `search_related_concepts()` — find related topics
- `get_temporal_context()` — historical topic evolution

**Topic relationships are denormalized** into `related_topic_ids` (JSON column) for fast reads. The graph is the canonical relationship store; the JSON column is a cache refreshed on compilation.

### D7: Compilation in Pipeline with Skip Option

**Decision**: KB compilation runs automatically after theme analysis in `aca pipeline daily`, with a `--skip-kb` flag to bypass it.

**Rationale**: Topics should stay fresh without manual intervention. The incremental compiler only processes new evidence, adding ~30-60s to the pipeline. Users who don't want KB compilation can skip it.

**Pipeline step ordering**:
```
aca pipeline daily:
  1. Ingest sources        (existing)
  2. Summarize pending     (existing)
  3. Analyze themes        (existing)
  4. Compile knowledge base (NEW — incremental)
  5. Create digest         (existing — can now reference Topic articles)
```

## Data Model

### Entity-Relationship Diagram

```
┌─────────────────────────────────┐
│             Topic               │
├─────────────────────────────────┤
│ id (PK)                        │
│ slug (unique, indexed)         │
│ name                           │
│ category (ThemeCategory enum)  │
│ status (TopicStatus enum)      │
│ summary (Text)                 │
│ article_md (Text)              │
│ article_version (Integer)      │
│ trend (ThemeTrend enum)        │
│ relevance_score (Float)        │
│ strategic_relevance (Float)    │
│ tactical_relevance (Float)     │
│ novelty_score (Float)          │
│ cross_functional_impact (Float)│
│ mention_count (Integer)        │
│ source_content_ids (JSON)      │
│ source_summary_ids (JSON)      │
│ source_theme_ids (JSON)        │
│ related_topic_ids (JSON)       │
│ key_points (JSON)              │
│ parent_topic_id (FK → Topic)   │
│ merged_into_id (FK → Topic)    │
│ first_evidence_at (DateTime)   │
│ last_evidence_at (DateTime)    │
│ last_compiled_at (DateTime)    │
│ compilation_model (String)     │
│ compilation_token_usage (Int)  │
│ created_at (DateTime)          │
│ updated_at (DateTime)          │
├─────────────────────────────────┤
│ INDEXES:                       │
│  ix_topics_slug (unique)       │
│  ix_topics_category            │
│  ix_topics_status              │
│  ix_topics_trend               │
│  ix_topics_relevance           │
│  ix_topics_last_compiled       │
│  ix_topics_category_trend      │
│    (category, trend)           │
└──────────┬──────────┬──────────┘
           │          │
    ┌──────┘          └──────┐
    │ parent_topic_id        │ 1:N
    │ (self-referential)     │
    ▼                        ▼
┌─────────────────────────────────┐
│           TopicNote             │
├─────────────────────────────────┤
│ id (PK)                        │
│ topic_id (FK → Topic, indexed) │
│ note_type (String)             │
│ content (Text)                 │
│ author (String)                │
│ filed_back (Boolean)           │
│ created_at (DateTime, indexed) │
└─────────────────────────────────┘
```

### TopicStatus Enum

```python
class TopicStatus(StrEnum):
    DRAFT = "draft"        # LLM-generated, not yet reviewed
    ACTIVE = "active"      # Live in the knowledge base
    STALE = "stale"        # No new evidence in >N days
    ARCHIVED = "archived"  # Manually or auto-archived
    MERGED = "merged"      # Merged into another topic
```

## Service Layer Design

### KB Compiler (`src/services/kb_compiler.py`)

```python
class KBCompiler:
    """Incremental knowledge base compiler."""
    
    async def compile(
        self,
        db: AsyncSession,
        full: bool = False,
        topic_slug: str | None = None,
    ) -> CompilationResult:
        """
        Main compilation entry point.
        
        1. Gather evidence (new ThemeAnalysis, content, notes)
        2. Match to existing topics
        3. Compile articles via LLM
        4. Update relationships via GraphitiClient
        5. Regenerate indices
        """
    
    async def _gather_evidence(self, db, since: datetime | None) -> list[Evidence]:
        """Collect new ThemeAnalysis results, content items, and unfiled TopicNotes."""
    
    async def _match_topic(self, db, theme_name: str) -> Topic | None:
        """Exact name match → embedding similarity → None (new topic)."""
    
    async def _compile_article(self, topic: Topic, evidence: list[Evidence]) -> str:
        """LLM generates/updates markdown article for a topic."""
    
    async def _update_relationships(self, topic: Topic, related: list[Topic]) -> None:
        """Sync topic relationships to GraphitiClient and denormalize."""
```

### KB Index Generator (`src/services/kb_index_generator.py`)

```python
class KBIndexGenerator:
    """Generates auto-maintained index files as special Topic records."""
    
    async def regenerate_all(self, db: AsyncSession) -> None:
        """Regenerate all index records."""
    
    async def _generate_master_index(self, db, topics: list[Topic]) -> str:
        """All topics with 1-line summaries, alphabetically sorted."""
    
    async def _generate_category_index(self, db, topics: list[Topic]) -> str:
        """Topics grouped by ThemeCategory."""
    
    async def _generate_trend_index(self, db, topics: list[Topic]) -> str:
        """Topics grouped by ThemeTrend."""
    
    async def _generate_relationship_map(self, db, topics: list[Topic]) -> str:
        """Topic adjacency list for navigation."""
```

### KB Health Check (`src/services/kb_health.py`)

```python
class KBHealthCheck:
    """Knowledge base quality analysis and auto-fix."""
    
    async def run(self, db: AsyncSession, fix: bool = False) -> HealthReport:
        """Run all health checks, optionally auto-fixing issues."""
    
    async def _check_stale(self, db, threshold_days: int = 30) -> list[Finding]:
    async def _check_merge_candidates(self, db, threshold: float = 0.90) -> list[Finding]:
    async def _check_coverage_gaps(self, db, min_per_category: int = 3) -> list[Finding]:
    async def _check_article_quality(self, db) -> list[Finding]:
```

## Prompt Design

KB compilation uses a structured prompt template stored in `settings/prompts.yaml`:

```yaml
knowledge_base:
  compile_article: |
    You are compiling a knowledge base article about "{topic_name}" for an AI/Data newsletter aggregator.
    
    ## Current Article (if updating)
    {existing_article}
    
    ## New Evidence
    {evidence_summaries}
    
    ## Related Topics
    {related_topics}
    
    ## Instructions
    Generate a comprehensive markdown article with these sections:
    - **Overview**: 2-3 paragraph introduction to the topic
    - **Key Developments**: Chronological summary of major developments
    - **Current State**: Where things stand today
    - **Related Topics**: How this connects to other topics (use [[Topic Name]] wikilinks)
    - **Sources**: Reference specific content items by title
    
    The article should be factual, well-structured, and reference specific evidence.
    Keep it under 2000 words. Use markdown formatting.
```

## Settings Configuration

New file `settings/knowledge_base.yaml`:

```yaml
# Knowledge Base Configuration
# Last updated: 2026-04-04

compilation:
  staleness_threshold_days: 30          # Days without evidence before marking stale
  semantic_match_threshold: 0.85        # Embedding similarity for topic matching
  merge_candidate_threshold: 0.90       # Similarity threshold for merge suggestions
  max_topics_per_compile: 50            # Limit per incremental run
  max_evidence_per_topic: 20            # Content items to consider per topic article
  min_coverage_per_category: 3          # Minimum topics per category before flagging gap

indices:
  auto_regenerate: true                 # Regenerate indices after each compilation
  index_types:                          # Which indices to maintain
    - _index
    - _by_category
    - _by_trend
    - _relationship_map

health_check:
  auto_stale: false                     # Auto-mark stale topics (vs just report)
  auto_merge: false                     # Auto-merge candidates (vs just report)
  quality_threshold: 0.7                # Minimum article quality score
```
