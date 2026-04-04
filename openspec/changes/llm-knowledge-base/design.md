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

### D2: Topic Model as Full Superset of ThemeData with Dedicated Category Table

**Decision**: The `Topic` SQLAlchemy model includes ALL fields from the `ThemeData` Pydantic model as individual database columns. Categories use a dedicated `TopicCategory` table (not the fixed `ThemeCategory` enum) enabling hierarchical, extensible taxonomy without migrations.

**Rationale**: Direct column storage enables:
- SQL-level filtering: `WHERE category_id = 5 AND trend = 'emerging' AND relevance_score > 0.7`
- Database indexes on frequently queried fields
- No JSON path queries or post-fetch filtering
- Clear schema evolution via Alembic migrations

**TopicCategory table** replaces the fixed `ThemeCategory` enum for topic categorization:
- `id`, `slug`, `name`, `description`, `parent_id` (self-referential FK), `icon`, `color`, `display_order`
- Seeded with 8 existing ThemeCategory values as top-level categories
- Hierarchical: `ML/AI → LLMs → Fine-tuning` via parent_id chain
- Maps directly to Obsidian folder structure
- New categories added via API/CLI — no `ALTER TYPE` migration needed

**Fields promoted from ThemeData**:
| ThemeData field | Topic column | Type |
|----------------|-------------|------|
| name | name | String(500) |
| description | summary | Text |
| category | category_id | FK → TopicCategory |
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

### D8: Obsidian Export — Category Hierarchy as Folder Structure

**Decision**: The Obsidian export maps TopicCategory hierarchy directly to the folder structure. Each topic is a `.md` file with YAML frontmatter placed in its category's folder. Wikilinks connect related topics. Indices are exported as root-level `_index.md` files.

**Vault structure** — Three-tier navigation: Category → Topic → Source → Extracts

```
vault/
├── _index.md                                  # Master index
├── _by_category.md                            # Category index
├── _by_trend.md                               # Trend index
├── _relationship_map.md                       # Topic adjacency map
├── summaries/                                 # Flat summary reference layer
│   ├── 2026-03-15-rag-evolution.md            # Full summary (linked from extracts)
│   └── 2026-02-20-rag-patterns.md
├── content/                                   # Content stubs with original URLs
│   ├── 2026-03-15-rag-evolution.md            # Stub → original content URL
│   └── 2026-02-20-rag-patterns.md
├── ML-AI/                                     # Top-level category folder
│   ├── RAG-Architecture/                      # Topic folder (not a single .md)
│   │   ├── _overview.md                       # LLM-compiled topic article
│   │   ├── The-Batch/                         # Source publication subfolder
│   │   │   └── 2026-03-15-rag-evolution.md    # Summary extract + [[link]]
│   │   ├── Simon-Willison/                    # Source blog subfolder
│   │   │   └── 2026-02-20-rag-patterns.md
│   │   └── ArXiv/                             # Source subfolder
│   │       └── 2026-01-10-dense-retrieval.md
│   └── LLMs/                                  # Subcategory folder
│       └── Fine-Tuning/                       # Topic folder
│           ├── _overview.md
│           ├── Latent-Space/
│           │   └── 2026-03-01-lora-at-scale.md
│           └── The-Batch/
│               └── 2026-02-28-ft-vs-rag.md
├── DevOps-Infra/
│   └── Kubernetes-AI-Workloads/
│       ├── _overview.md
│       └── InfoQ/
│           └── 2026-03-20-k8s-gpu.md
└── ...
```

**Three file types in the vault:**

| File | Location | Content |
|------|----------|---------|
| `_overview.md` | `Category/Topic/` | LLM-compiled topic article with YAML frontmatter, wikilinks to related topics |
| Source extract | `Category/Topic/Source/` | Key points from one summary + `[[summaries/slug]]` wikilink |
| Summary file | `summaries/` | Full summary markdown + `[[content/slug]]` wikilink |
| Content stub | `content/` | Title, date, source URL, publication — links to original content |

**Link chain:** Topic `_overview.md` → Source extract → `[[summaries/slug]]` → `[[content/slug]]` → original URL

This enables three browsing patterns in Obsidian:
1. **Topic-first**: Open `ML-AI/RAG-Architecture/_overview.md` → see compiled knowledge → drill into source evidence
2. **Source-first**: Browse `ML-AI/RAG-Architecture/The-Batch/` → see all evidence from one publication
3. **Graph view**: Wikilinks between topics, summaries, and content create a navigable knowledge graph

**Rationale**:
- Category hierarchy as folders gives Obsidian users natural navigation via the file explorer
- YAML frontmatter enables Obsidian Dataview queries (`TABLE relevance_score FROM "ML-AI"`)
- Wikilinks (`[[Topic Name]]`) power Obsidian's graph view for relationship visualization
- This is significantly richer than flat folder + frontmatter — the hierarchy IS the knowledge structure

**Topic `_overview.md` format**:
```markdown
---
slug: rag-architecture
name: RAG Architecture
category_path: ML/AI
trend: growing
status: active
relevance_score: 0.87
mention_count: 15
article_version: 3
sources: [The-Batch, Simon-Willison, ArXiv]
first_evidence_at: 2025-11-15T00:00:00Z
last_evidence_at: 2026-04-01T00:00:00Z
last_compiled_at: 2026-04-04T12:00:00Z
tags: [retrieval-augmented-generation, vector-databases, embedding]
---

# RAG Architecture

## Overview
[LLM-compiled article content synthesizing all source evidence...]

## Key Developments
- 2026-03: Evolution toward agentic RAG patterns ([[The-Batch/2026-03-15-rag-evolution]])
- 2026-02: Practical patterns for production RAG ([[Simon-Willison/2026-02-20-rag-patterns]])
- 2026-01: Dense retrieval advances ([[ArXiv/2026-01-10-dense-retrieval]])

## Related Topics
- [[../../ML-AI/Fine-Tuning/_overview|Fine-Tuning]] — complementary approach
- [[../../ML-AI/Vector-Databases/_overview|Vector Databases]] — key infrastructure
```

**Source extract format** (`Category/Topic/Source/date-slug.md`):
```markdown
---
summary_slug: 2026-03-15-rag-evolution
source: The Batch
published: 2026-03-15
content_id: 1234
---

## Key Points
- RAG is evolving toward agentic patterns where retrieval is tool-based
- Hybrid approaches combining RAG + fine-tuning show best results

Full summary: [[summaries/2026-03-15-rag-evolution]]
```

**Three integration modes** (all share the same frontmatter format and folder structure):

| Mode | Transport | When to Use | Implemented |
|------|-----------|-------------|-------------|
| **Mode 2: File Export** | Write `.md` files to directory | Local use, no Obsidian CLI | This change |
| **Mode 1: CLI-Driven** | `obsidian create/append/property:set` | Local with Obsidian 1.12+ | Deferred |
| **Mode 3: Headless Sync** | File export + `obsidian-headless sync` | Server deployment (Railway) | Deferred |

**Bidirectional sync** (Mode 3, deferred): The official Obsidian CLI's `obsidian read` command enables detecting user edits in the vault. Combined with `obsidian-headless` for server-side sync, this creates a full round-trip: DB → export → Obsidian Sync → user edits → `obsidian read` → `aca kb import` → DB. The frontmatter `slug` field is the reconciliation key.

**CLI compatibility**: The frontmatter format is designed to be CLI-compatible from day one. The `obsidian property:set` command can update individual frontmatter fields without touching the article body — enabling selective sync of metadata (trend, scores) without rewriting content.

**Alternative rejected**: Flat structure with frontmatter-only categorization. While simpler, it loses the visual organization that makes Obsidian useful for knowledge navigation. The category hierarchy is the core UX differentiator.

## Data Model

### Entity-Relationship Diagram

```
┌─────────────────────────────────┐
│         TopicCategory           │
├─────────────────────────────────┤
│ id (PK)                        │
│ slug (unique, indexed)         │
│ name                           │
│ description (Text, nullable)   │
│ parent_id (FK → self, nullable)│
│ icon (String, nullable)        │
│ color (String, nullable)       │
│ display_order (Integer, def 0) │
│ created_at (DateTime)          │
├─────────────────────────────────┤
│ INDEXES:                       │
│  uq_topic_categories_slug      │
│  ix_topic_categories_parent    │
└──────────┬──────────────────────┘
           │ 1:N
           ▼
┌─────────────────────────────────┐
│             Topic               │
├─────────────────────────────────┤
│ id (PK)                        │
│ slug (unique, indexed)         │
│ name                           │
│ category_id (FK → TopicCategory)│
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
