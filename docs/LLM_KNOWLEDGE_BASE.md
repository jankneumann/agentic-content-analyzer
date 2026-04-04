# LLM Knowledge Base

An LLM-compiled knowledge base that promotes **topics and concepts** to first-class entities, enabling incremental compilation, self-maintaining indices, Q&A, and health checks — inspired by [Andrei Karpathy's approach](https://x.com/karpathy/status/1908190230636302686) to building personal knowledge bases with LLMs.

## Design Philosophy

The system follows a **"compile, don't just collect"** approach: raw content from diverse sources is not merely stored — it is incrementally compiled by an LLM into a structured, interlinked knowledge base where **topics are the primary organizing unit** and content items are evidence.

```
Raw Sources ──→ Content (exists) ──→ Summaries (exists) ──→ Theme Extraction (exists)
                                                                      │
                                                              ┌───────▼────────┐
                                                              │  KB Compilation │ ◄── NEW
                                                              │  (incremental)  │
                                                              └───────┬────────┘
                                                                      │
                                              ┌───────────────────────┼───────────────────────┐
                                              │                       │                       │
                                    ┌─────────▼──────┐    ┌──────────▼─────────┐   ┌─────────▼────────┐
                                    │  Topic Articles │    │  Index Generation  │   │  Health Checks   │
                                    │  (.md per topic)│    │  (auto-maintained) │   │  (lint & enrich) │
                                    └─────────┬──────┘    └──────────┬─────────┘   └─────────┬────────┘
                                              │                      │                       │
                                              └──────────────────────┼───────────────────────┘
                                                                     │
                                              ┌──────────────────────┼──────────────────────┐
                                              │                      │                      │
                                     ┌────────▼───────┐   ┌─────────▼────────┐   ┌─────────▼────────┐
                                     │   API / MCP    │   │   CLI (aca kb)   │   │  Obsidian Export  │
                                     │   endpoints    │   │   commands       │   │  (bidirectional)  │
                                     └────────────────┘   └──────────────────┘   └──────────────────┘
```

## Core Design Decision: Database vs. Markdown Files

Karpathy's approach uses a **directory of .md files** navigated directly by an LLM in Obsidian. We need to decide where our source of truth lives.

### Option A: Flat Markdown Files (Karpathy's approach)

| Dimension | Assessment |
|-----------|------------|
| **LLM navigation** | LLMs can read directories, follow relative links, and grep files directly |
| **Simplicity** | No schema, no migrations — just files |
| **Obsidian native** | Files ARE the Obsidian vault; zero export/sync needed |
| **Version control** | Git-friendly; diffs are human-readable |
| **Scalability** | Degrades past ~1000 articles; file enumeration becomes expensive |
| **Search** | No semantic search — relies on LLM reading index files or naive grep |
| **Relationships** | Wikilinks (`[[Topic]]`) only — no typed relationships, no confidence scores |
| **Multi-user** | Single-user; no concurrent access, no permissions |
| **Structured queries** | Impossible — "find all EMERGING topics in ML_AI" requires reading every file |
| **Integration** | Disconnected from existing pipeline (digests, agents, search) |

### Option B: Database as Source of Truth + Obsidian as Interface (our approach)

| Dimension | Assessment |
|-----------|------------|
| **LLM navigation** | LLM uses hybrid search, tree indices, and graph queries (already built) |
| **Schema** | Typed Topic model with category, trend, confidence, relationships |
| **Obsidian** | Export layer generates vault; edits written back via MCP tools |
| **Version control** | Topic versioning in DB; Obsidian vault is derived (can be regenerated) |
| **Scalability** | PostgreSQL + pgvector + knowledge graph handle 100K+ topics |
| **Search** | Hybrid BM25 + vector search across all KB content (already built) |
| **Relationships** | Typed, weighted, temporal relationships in graph (Graphiti) |
| **Multi-user** | API-native; permissions, sharing, concurrent access |
| **Structured queries** | Full SQL + graph queries for any dimension |
| **Integration** | Topics feed into digests, agents, Q&A, voice mode — all existing infra |

### Decision: Option B — Database-first with Obsidian export

The database is the canonical representation. Obsidian is one of several interfaces (alongside the web frontend, CLI, MCP tools, and voice mode). The export to Obsidian generates:

- `.md` files per topic with YAML frontmatter (metadata)
- Wikilinks (`[[Related Topic]]`) generated from DB relationships
- Index files (`_index.md`, `_by_category.md`, etc.) generated from DB queries
- Images and diagrams referenced via relative paths

Edits made in Obsidian can be synced back via:
- MCP tools (`update_topic`, `add_topic_note`)
- CLI (`aca kb import --from-obsidian <vault-path>`)
- File watcher (future: detect changes and sync)

### Interaction with Graph Backend Abstraction

The Topic/Concept entities stored in the knowledge graph are **graph-backend-agnostic**. The ongoing Graphiti abstraction (Neo4j → FalkorDB) means:

- Topic relationships are stored via Graphiti's entity/relationship API
- No direct Cypher or FalkorDB queries — all access through the `GraphitiClient` abstraction
- The KB compilation service interacts with `GraphitiClient`, not a specific database
- Topic entity extraction reuses the existing Graphiti episode pipeline

## Data Model

### Topic (New SQLAlchemy Model)

The `Topic` model is the first-class knowledge entity. Unlike `ThemeData` (which is an ephemeral Pydantic model embedded as JSON in `ThemeAnalysis`), `Topic` is a persistent, versioned, independently queryable entity.

```python
class TopicStatus(StrEnum):
    DRAFT = "draft"            # LLM-generated, not yet reviewed
    ACTIVE = "active"          # Live in the knowledge base
    STALE = "stale"            # No new evidence in >N days
    ARCHIVED = "archived"      # Manually or auto-archived
    MERGED = "merged"          # Merged into another topic

class Topic(Base):
    __tablename__ = "topics"

    id              = Column(Integer, PK)
    slug            = Column(String(200), unique, indexed)        # URL-safe identifier
    name            = Column(String(500), not null)               # Display name
    category        = Column(Enum(ThemeCategory))                 # Reuse existing enum
    status          = Column(Enum(TopicStatus), default=DRAFT)
    
    # LLM-compiled article content
    summary         = Column(Text)                                # 2-3 sentence summary
    article_md      = Column(Text)                                # Full markdown article
    article_version = Column(Integer, default=1)                  # Incremented on recompile
    
    # Trend & scoring (promoted from ThemeData)
    trend           = Column(Enum(ThemeTrend))
    relevance_score = Column(Float)
    novelty_score   = Column(Float)
    mention_count   = Column(Integer, default=0)
    
    # Evidence links
    source_content_ids   = Column(JSON)                           # Content items supporting this topic
    source_summary_ids   = Column(JSON)                           # Summaries referencing this topic
    source_theme_ids     = Column(JSON)                           # ThemeAnalysis records
    
    # Relationships (denormalized for fast queries; canonical in graph)
    related_topic_ids    = Column(JSON)                           # List[int] — related Topic IDs
    parent_topic_id      = Column(FK → Topic, nullable)           # Hierarchy: "RAG" → parent "LLM"
    merged_into_id       = Column(FK → Topic, nullable)           # If status=MERGED
    
    # Compilation metadata
    last_compiled_at     = Column(DateTime)
    last_evidence_at     = Column(DateTime)                       # Most recent source content date
    compilation_model    = Column(String(100))                    # Which LLM compiled it
    compilation_token_usage = Column(Integer)
    
    # Timestamps
    created_at      = Column(DateTime)
    updated_at      = Column(DateTime)
```

### TopicNote (User/Agent annotations)

```python
class TopicNote(Base):
    __tablename__ = "topic_notes"

    id          = Column(Integer, PK)
    topic_id    = Column(FK → Topic, not null, indexed)
    note_type   = Column(String(50))    # "observation", "question", "correction", "insight"
    content     = Column(Text)
    author      = Column(String(100))   # "system", "agent:<persona>", "user"
    filed_back  = Column(Boolean)       # Whether this was incorporated into the article
    created_at  = Column(DateTime)
```

### Relationship to Existing Models

```
Content (raw source)
  └── Summary (per-content analysis)
        └── ThemeAnalysis (cross-content themes — ephemeral)
              └── Topic (persistent KB entity) ◄── NEW
                    ├── TopicNote (annotations) ◄── NEW
                    ├── related Topics (graph + denormalized)
                    ├── parent Topic (hierarchy)
                    └── → Digest (topics feed digest creation)
                    └── → AgentInsight (topics enrich agent analysis)
                    └── → Search (topics are searchable via hybrid search)
```

## KB Compilation Pipeline

### Incremental Compilation

The compiler runs after theme extraction (or on demand) and **updates existing topics** rather than creating new ones each time.

```
1. Gather new evidence
   ├── Recent ThemeAnalysis results (since last compilation)
   ├── New content items mentioning known topics
   └── Agent insights tagged with topic names

2. Match to existing topics
   ├── Exact name match → update existing
   ├── Semantic similarity (embedding) → merge candidate
   └── No match → create new DRAFT topic

3. Compile/recompile articles
   ├── Gather all evidence for the topic (content, summaries, notes)
   ├── Query knowledge graph for entity relationships
   ├── LLM generates/updates article markdown
   ├── LLM generates 2-3 sentence summary
   └── Increment article_version

4. Update relationships
   ├── Detect related topics (co-occurrence + semantic similarity)
   ├── Detect parent-child hierarchies (LLM classification)
   ├── Sync to knowledge graph (Graphiti episodes)
   └── Denormalize into related_topic_ids

5. Regenerate indices
   ├── Master index (_index.md equivalent in DB)
   ├── Category indices
   ├── Trend-based indices (emerging, declining)
   └── Recency-based indices
```

### Auto-Maintained Indices

Inspired by Karpathy's observation that LLMs maintain their own index files for self-navigation. Our indices are **database views + cached markdown** that the LLM can read to orient itself:

| Index | Purpose | Storage |
|-------|---------|---------|
| **Master index** | All topics with 1-line summaries | Cached markdown, regenerated on compile |
| **Category index** | Topics grouped by ThemeCategory | Cached markdown |
| **Trend index** | Topics grouped by ThemeTrend | Cached markdown |
| **Recency index** | Recently updated topics | Dynamic query |
| **Relationship map** | Topic → related topics (adjacency list) | Cached markdown |
| **Coverage gaps** | Categories with few/stale topics | Generated by health check |

These indices serve dual purposes:
1. **LLM self-navigation**: Agent reads the master index to decide which topics to explore
2. **Obsidian export**: Indices become `_index.md` files in the vault

## KB Q&A Mode

An agent mode where questions are answered **against the compiled KB** (not raw content), and answers are optionally filed back as TopicNotes.

```
User: "What are the current trade-offs between RAG and fine-tuning?"

1. Agent reads master index → identifies relevant topics
2. Agent reads topic articles for "RAG Architecture" and "Fine-tuning"
3. Agent queries graph for relationships between the two
4. Agent synthesizes answer as markdown
5. Agent optionally files answer as TopicNote on both topics
   (so future queries benefit from this analysis)
```

### Integration with Voice Mode

The existing WebSocket STT + SSE streaming + TTS pipeline supports interactive voice Q&A:

```
Voice input → Cloud STT → KB Q&A agent → TTS → Audio response
```

For Friedman's "focused mini-KB for a run" pattern:
- `aca kb export --topic "RAG Architecture" --depth 2 --format audio-brief`
- Generates a focused text brief from topic + related topics (depth=2)
- Runs through TTS pipeline for offline listening

## KB Health Checks & Linting

Periodic LLM sweeps over the knowledge base to maintain quality:

| Check | What it does |
|-------|-------------|
| **Stale detection** | Topics with no new evidence in >30 days → mark STALE |
| **Consistency** | Compare topic articles for contradictory claims |
| **Coverage gaps** | Identify categories with low topic density |
| **Merge candidates** | Find topics with high semantic similarity (potential duplicates) |
| **Missing connections** | Topics that should be related but aren't linked |
| **Factuality** | Cross-reference claims with source content |
| **Article quality** | Score articles on completeness, clarity, depth |

Output: A health report (markdown) with actionable recommendations that can be auto-applied or reviewed.

## Interface Layer: CLI, API, MCP

### CLI Commands (`aca kb`)

```bash
# Compilation
aca kb compile                          # Incremental compile (new evidence only)
aca kb compile --full                   # Full recompile of all topics
aca kb compile --topic "RAG"            # Recompile specific topic

# Browsing
aca kb list                             # List all active topics
aca kb list --category ml_ai --trend emerging
aca kb show <slug>                      # Show topic article
aca kb index                            # Show master index

# Q&A
aca kb query "question"                 # Ask the KB a question
aca kb query "question" --file-back     # Ask and file answer as TopicNote

# Health
aca kb lint                             # Run health checks
aca kb lint --fix                       # Auto-fix issues (merge dupes, update stale)

# Export
aca kb export --format obsidian --output ./vault
aca kb export --format html --topic "RAG"
aca kb export --format audio-brief --topic "RAG" --depth 2
```

### API Endpoints (`/api/v1/kb/`)

```
GET    /api/v1/kb/topics                 # List topics (filterable)
GET    /api/v1/kb/topics/:slug           # Get topic article
POST   /api/v1/kb/topics                 # Create topic (manual)
PATCH  /api/v1/kb/topics/:slug           # Update topic
DELETE /api/v1/kb/topics/:slug           # Archive topic

GET    /api/v1/kb/topics/:slug/notes     # List notes for topic
POST   /api/v1/kb/topics/:slug/notes     # Add note to topic

POST   /api/v1/kb/compile                # Trigger compilation
GET    /api/v1/kb/index                  # Get master index
GET    /api/v1/kb/health                 # Run health check

POST   /api/v1/kb/query                  # Q&A against KB
GET    /api/v1/kb/export/obsidian        # Export as Obsidian vault (zip)
```

### MCP Tools

```python
@mcp.tool()
def search_knowledge_base(query: str, limit: int = 10) -> str:
    """Search the compiled knowledge base for topics."""

@mcp.tool()
def get_topic(slug: str) -> str:
    """Get a topic article from the knowledge base."""

@mcp.tool()
def update_topic(slug: str, section: str, content: str) -> str:
    """Update a section of a topic article."""

@mcp.tool()
def add_topic_note(slug: str, note: str, note_type: str = "observation") -> str:
    """Add a note to a topic (for filing insights back into the KB)."""

@mcp.tool()
def get_kb_index(category: str | None = None) -> str:
    """Get the knowledge base index (master or by category)."""

@mcp.tool()
def compile_knowledge_base(topic_slug: str | None = None) -> str:
    """Trigger KB compilation (incremental or for a specific topic)."""
```

## Relationship to Existing Tree Index

The existing `TreeIndexChunkingStrategy` builds hierarchical summaries from document headings — conceptually similar to Karpathy's LLM-compiled indices. The key difference:

| Aspect | Tree Index (existing) | KB Index (new) |
|--------|----------------------|----------------|
| **Scope** | Per-document | Cross-document (per-topic) |
| **Unit** | Headings within one article | Topics across all content |
| **Purpose** | Search retrieval | Knowledge navigation |
| **Updates** | Once (at chunking time) | Incremental (on every compile) |

The two systems are complementary:
- **Tree index** helps find specific passages within a document
- **KB index** helps navigate the knowledge landscape across all documents
- The KB compiler can use tree indices to efficiently read relevant sections when compiling topic articles

## Pipeline Integration

The KB compilation step slots into the existing pipeline:

```bash
# Existing pipeline
aca pipeline daily    # ingest → summarize → theme-analyze → digest

# Enhanced pipeline
aca pipeline daily    # ingest → summarize → theme-analyze → KB compile → digest
                      #                                         ↑ NEW STEP
```

The digest creator can then reference compiled topics for richer context:
- Instead of ephemeral ThemeData, digests link to persistent Topic entities
- Historical context comes from topic evolution (article_version history)
- Cross-references between digest sections and KB articles

## Implementation Plan

### Phase 1: Data Model & Compilation (this PR)
1. Topic + TopicNote SQLAlchemy models + Alembic migration
2. KB compilation service (incremental)
3. Index generation service
4. CLI commands (`aca kb compile/list/show/index`)
5. Settings and prompts YAML

### Phase 2: Q&A & Health Checks
6. KB Q&A agent mode (KnowledgeBase specialist or Research extension)
7. Health check / linting service
8. API endpoints
9. MCP tool exposure

### Phase 3: Export & Integration
10. Obsidian export (vault generation)
11. Pipeline integration (KB compile step in daily pipeline)
12. Voice mode integration (focused audio briefs)
13. Obsidian import / sync-back via MCP
