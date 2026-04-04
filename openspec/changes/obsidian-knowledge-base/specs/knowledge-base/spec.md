# knowledge-base

Knowledge base compilation, topic management, indices, Q&A, and health checks.

## ADDED Requirements

### Requirement: Topic Data Model

The system SHALL provide persistent Topic and TopicNote SQLAlchemy models with Alembic migration.

A Topic SHALL have: slug (unique), name, category (ThemeCategory enum), status (TopicStatus enum: draft/active/stale/archived/merged), summary, article_md, article_version, trend (ThemeTrend enum), relevance_score, novelty_score, mention_count, source_content_ids (JSON), source_summary_ids (JSON), source_theme_ids (JSON), related_topic_ids (JSON), parent_topic_id (FK self-ref), merged_into_id (FK self-ref), last_compiled_at, last_evidence_at, compilation_model, compilation_token_usage, created_at, updated_at.

A TopicNote SHALL have: topic_id (FK), note_type (observation/question/correction/insight), content, author, filed_back (boolean), created_at.

#### Scenario: Create topic from theme analysis

WHEN the KB compilation service processes a new ThemeAnalysis result
AND no existing topic matches the theme name or semantic embedding
THEN a new Topic with status=draft SHALL be created
AND source_theme_ids SHALL include the ThemeAnalysis ID

#### Scenario: Topic slug uniqueness

WHEN a topic is created with a name that generates a duplicate slug
THEN the system SHALL append a numeric suffix to ensure uniqueness
AND the slug SHALL be URL-safe (lowercase, hyphens, no special characters)

#### Scenario: Topic note creation

WHEN a TopicNote is added to a topic
THEN the note SHALL reference the topic via topic_id FK
AND the author field SHALL identify the source (system, agent:<persona>, user)

### Requirement: KB Compilation Service

The system SHALL provide a KnowledgeBaseService that incrementally compiles topics from theme analysis results, summaries, and content items.

The compilation pipeline SHALL: (1) gather new evidence since last compilation, (2) match evidence to existing topics via exact name match and semantic similarity, (3) compile or recompile topic articles via LLM, (4) detect and update topic relationships and hierarchies, (5) regenerate indices.

#### Scenario: Incremental compilation

WHEN `aca kb compile` is invoked
THEN the service SHALL gather ThemeAnalysis results created since last_compiled_at
AND match themes to existing topics using exact name match first
AND fall back to semantic similarity (embedding cosine distance) for fuzzy matching
AND compile article markdown for new or updated topics via LLM
AND update last_compiled_at timestamp

#### Scenario: Full recompilation

WHEN `aca kb compile --full` is invoked
THEN the service SHALL recompile ALL active topics regardless of last_compiled_at
AND increment article_version for each recompiled topic

#### Scenario: Single topic compilation

WHEN `aca kb compile --topic <slug>` is invoked
THEN the service SHALL recompile only the specified topic
AND gather all evidence (content, summaries, themes, notes) for that topic
AND increment article_version

#### Scenario: Semantic topic matching

WHEN a theme name does not exactly match any existing topic
AND the theme embedding has cosine similarity > 0.85 with an existing topic
THEN the service SHALL match the theme to the existing topic
AND add the new evidence to the existing topic's source IDs

#### Scenario: Topic merge detection

WHEN two topics have cosine similarity > 0.90 between their compiled articles
THEN the service SHALL flag them as merge candidates
AND NOT automatically merge (merge requires explicit action)

#### Scenario: Compilation with no new evidence

WHEN compilation is invoked but no new ThemeAnalysis results exist since last run
THEN the service SHALL complete without error
AND report zero topics compiled

#### Scenario: LLM failure during compilation

WHEN the LLM call fails during topic article compilation
THEN the service SHALL log the error with topic slug and error details
AND skip the failed topic
AND continue compiling remaining topics
AND report the failure in the compilation summary

### Requirement: Topic Relationship Management

The system SHALL maintain topic relationships using DB columns as the canonical store, with optional Graphiti sync when a graph backend is available.

#### Scenario: DB-only relationship storage

WHEN a topic relationship is detected during compilation
THEN related_topic_ids JSON column SHALL be updated on both topics
AND parent_topic_id FK SHALL be set for hierarchical relationships

#### Scenario: Optional graph sync

WHEN a graph backend (Neo4j/FalkorDB via Graphiti) is available
THEN topic relationships SHALL also be synced to the knowledge graph
AND Graphiti episode API SHALL be used (not direct Cypher queries)

#### Scenario: Graph backend unavailable

WHEN the graph backend is not available during compilation
THEN the service SHALL log a warning
AND continue with DB-only relationship storage
AND NOT fail the compilation

### Requirement: Index Generation

The system SHALL generate and maintain auto-updated indices for KB navigation.

Indices SHALL include: master index (all topics with 1-line summaries), category index (grouped by ThemeCategory), trend index (grouped by ThemeTrend), recency index (recently updated).

#### Scenario: Index regeneration after compilation

WHEN a compilation cycle completes with at least one topic compiled
THEN all indices SHALL be regenerated
AND indices SHALL be stored as cached markdown in the database

#### Scenario: Master index content

WHEN the master index is generated
THEN it SHALL list all active topics sorted by relevance_score descending
AND each entry SHALL include: name, category, trend, 1-line summary, last_compiled_at

#### Scenario: Category index content

WHEN the category index is generated
THEN topics SHALL be grouped by ThemeCategory
AND within each category, topics SHALL be sorted by relevance_score descending

#### Scenario: Index retrieval

WHEN a user requests an index via CLI, API, or MCP
THEN the system SHALL return the cached markdown
AND the response SHALL include the index generation timestamp

### Requirement: KB CLI Commands

The system SHALL expose KB functionality via the `aca kb` CLI command group.

#### Scenario: List topics

WHEN `aca kb list` is invoked
THEN the system SHALL display all active topics with name, category, trend, and mention_count
AND support `--category`, `--trend`, `--status` filters
AND support `--json` output mode

#### Scenario: Show topic detail

WHEN `aca kb show <slug>` is invoked
THEN the system SHALL display the topic's compiled article markdown
AND include frontmatter metadata (status, trend, scores, dates)
AND support `--json` output mode

#### Scenario: Show index

WHEN `aca kb index` is invoked
THEN the system SHALL display the master index
AND support `--category` to show a specific category index

#### Scenario: Compile via CLI

WHEN `aca kb compile` is invoked
THEN the system SHALL run incremental compilation
AND display progress (topics found, compiled, skipped, failed)
AND support `--full` and `--topic <slug>` flags

### Requirement: KB API Endpoints

The system SHALL expose KB functionality via REST API at `/api/v1/kb/`.

All endpoints SHALL require authentication via the existing auth middleware.

#### Scenario: List topics endpoint

WHEN GET `/api/v1/kb/topics` is called
THEN the system SHALL return a paginated list of topics
AND support query parameters: category, trend, status, limit, offset
AND return 200 with topic array

#### Scenario: Get topic endpoint

WHEN GET `/api/v1/kb/topics/:slug` is called with a valid slug
THEN the system SHALL return the full topic including article_md
AND return 200

#### Scenario: Get topic not found

WHEN GET `/api/v1/kb/topics/:slug` is called with an unknown slug
THEN the system SHALL return 404

#### Scenario: Create topic endpoint

WHEN POST `/api/v1/kb/topics` is called with name and category
THEN the system SHALL create a new topic with status=draft
AND generate a unique slug from the name
AND return 201 with the created topic

#### Scenario: Update topic endpoint

WHEN PATCH `/api/v1/kb/topics/:slug` is called with valid fields
THEN the system SHALL update the specified fields
AND update updated_at timestamp
AND return 200

#### Scenario: Archive topic endpoint

WHEN DELETE `/api/v1/kb/topics/:slug` is called
THEN the system SHALL set status=archived (not hard delete)
AND return 204

#### Scenario: Topic notes endpoints

WHEN GET `/api/v1/kb/topics/:slug/notes` is called
THEN the system SHALL return all notes for the topic

WHEN POST `/api/v1/kb/topics/:slug/notes` is called with content and note_type
THEN the system SHALL create a TopicNote
AND return 201

#### Scenario: Compile endpoint

WHEN POST `/api/v1/kb/compile` is called
THEN the system SHALL trigger incremental compilation
AND return 202 with a compilation summary after completion

#### Scenario: Index endpoint

WHEN GET `/api/v1/kb/index` is called
THEN the system SHALL return the master index markdown
AND support `?category=` query parameter for category-specific index

### Requirement: KB MCP Tools

The system SHALL expose KB functionality via MCP tools for agent access.

#### Scenario: Search knowledge base tool

WHEN the `search_knowledge_base` MCP tool is called with a query
THEN the system SHALL search topics by name, summary, and article content
AND return matching topics with relevance scores

#### Scenario: Get topic tool

WHEN the `get_topic` MCP tool is called with a slug
THEN the system SHALL return the full topic article and metadata as JSON

#### Scenario: Update topic tool

WHEN the `update_topic` MCP tool is called with a slug and section content
THEN the system SHALL update the specified section of the topic article
AND increment article_version

#### Scenario: Add topic note tool

WHEN the `add_topic_note` MCP tool is called
THEN the system SHALL create a TopicNote with the specified content and type
AND set author to "agent:<caller>" or "system"

#### Scenario: Get KB index tool

WHEN the `get_kb_index` MCP tool is called
THEN the system SHALL return the master index (or category index if specified)

#### Scenario: Compile KB tool

WHEN the `compile_knowledge_base` MCP tool is called
THEN the system SHALL trigger compilation and return a summary

### Requirement: KB Q&A Mode

The system SHALL provide a Q&A mode where questions are answered against the compiled knowledge base rather than raw content.

#### Scenario: Question answering

WHEN a user submits a question via `aca kb query "question"` or POST `/api/v1/kb/query`
THEN the system SHALL search the master index to identify relevant topics
AND read the compiled articles for those topics
AND query topic relationships for additional context
AND synthesize an answer as markdown

#### Scenario: File-back mode

WHEN a Q&A query is invoked with `--file-back` flag (CLI) or `file_back: true` (API)
THEN the system SHALL file the answer as a TopicNote on each referenced topic
AND set note_type="insight" and author="system"
AND set filed_back=false (to be incorporated in next compilation)

#### Scenario: No relevant topics

WHEN a question has no matching topics in the KB
THEN the system SHALL respond with a message indicating no relevant KB content
AND suggest searching raw content instead

### Requirement: KB Health Checks

The system SHALL provide health checks and linting for KB quality maintenance.

#### Scenario: Stale topic detection

WHEN `aca kb lint` is invoked
THEN topics with no new evidence in >30 days SHALL be flagged as stale

#### Scenario: Merge candidate detection

WHEN `aca kb lint` is invoked
THEN topic pairs with article cosine similarity >0.90 SHALL be flagged as merge candidates

#### Scenario: Coverage gap detection

WHEN `aca kb lint` is invoked
THEN categories with fewer than 3 active topics SHALL be flagged as coverage gaps

#### Scenario: Auto-fix stale topics

WHEN `aca kb lint --fix` is invoked
THEN stale topics (>30 days, no new evidence) SHALL have status set to stale
AND a summary of changes SHALL be displayed

#### Scenario: Health report format

WHEN health checks complete
THEN the system SHALL produce a markdown report
AND the report SHALL be structured by check type (stale, merge candidates, coverage, quality)
AND each finding SHALL include the affected topic slug and recommended action

### Requirement: Obsidian Topic Export

The existing Obsidian exporter SHALL be extended to export compiled Topic articles in the 3-tier vault structure.

#### Scenario: Topic overview export

WHEN the Obsidian exporter runs and topics exist in the database
THEN each active topic SHALL be exported as `<Category>/<Topic>/_overview.md`
AND the file SHALL contain YAML frontmatter with topic metadata
AND the file SHALL contain the compiled article markdown
AND related topics SHALL be linked via wikilinks

#### Scenario: Source extract export

WHEN a topic has linked content items via source_content_ids
THEN source extracts SHALL be exported as `<Category>/<Topic>/<Source>/<date>-<slug>.md`
AND each extract SHALL link to the corresponding summary via wikilink

#### Scenario: Incremental topic export

WHEN the exporter runs with an existing manifest
THEN only topics with article_version > last exported version SHALL be re-exported
AND the manifest SHALL track topic article_version for change detection

#### Scenario: 3-tier vault structure

WHEN topics are exported
THEN the vault SHALL follow the structure: Category/Topic/_overview.md + Category/Topic/Source/extracts
AND a master `_index.md` SHALL be generated at the vault root
AND category index files SHALL be generated at each category folder

### Requirement: Model Configuration

The system SHALL use the existing `MODEL_*` settings pattern for KB LLM configuration.

#### Scenario: Default model settings

WHEN KB compilation runs without explicit model configuration
THEN the system SHALL use `MODEL_KB_COMPILATION` setting (default: claude-sonnet-4-5)
AND `MODEL_KB_INDEX` for index generation (default: claude-haiku-4-5)

#### Scenario: Model override

WHEN `MODEL_KB_COMPILATION` environment variable is set
THEN the compilation service SHALL use the specified model
AND the model name SHALL be recorded in the topic's compilation_model field

### Requirement: Pipeline Integration

The system SHALL optionally integrate KB compilation into the daily pipeline.

#### Scenario: Optional pipeline step

WHEN `aca pipeline daily` is invoked
AND KB compilation is enabled via settings
THEN KB compilation SHALL run after theme analysis and before digest creation

#### Scenario: Pipeline step disabled

WHEN KB compilation is disabled via settings (default)
THEN the pipeline SHALL skip the KB compilation step
AND no error SHALL be raised
