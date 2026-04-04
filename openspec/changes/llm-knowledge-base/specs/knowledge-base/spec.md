# knowledge-base Specification

## ADDED Requirements

### Requirement: Topic as first-class persistent entity

The system SHALL store topics as persistent SQLAlchemy records in a `topics` PostgreSQL table. Each topic SHALL have a unique `slug`, a display `name`, a `category_id` (foreign key to `TopicCategory`), a lifecycle `status` (TopicStatus enum), and LLM-compiled article content. The Topic model SHALL be a full superset of the existing `ThemeData` Pydantic model fields, promoted to individual database columns for direct queryability.

#### Scenario: Topic created from theme analysis

- **WHEN** the KB compiler processes a new theme from `ThemeAnalysis` that has no matching existing topic
- **THEN** a `Topic` record SHALL be created with `status=draft`, `article_version=1`, and all ThemeData fields populated (name, category, trend, relevance_score, novelty_score, strategic_relevance, tactical_relevance, mention_count, related_topic_ids)
- **AND** the `slug` SHALL be auto-generated from the topic name (lowercase, hyphenated, unique)

#### Scenario: Topic article compiled by LLM

- **WHEN** a topic is created or updated with new evidence
- **THEN** the `article_md` field SHALL contain an LLM-generated markdown article summarizing the topic with sections for overview, key developments, related topics, and source references
- **AND** the `summary` field SHALL contain a 2-3 sentence overview
- **AND** `article_version` SHALL be incremented on each recompilation
- **AND** `last_compiled_at` SHALL be updated to the current timestamp

#### Scenario: Topic lifecycle transitions

- **WHEN** a topic has `status=draft` and is reviewed or recompiled
- **THEN** the system SHALL support transitioning to `active`
- **WHEN** an active topic has no new evidence for longer than the configured staleness threshold (default 30 days)
- **THEN** the health check SHALL flag it as `stale`
- **WHEN** two topics are determined to be duplicates
- **THEN** the secondary topic SHALL be set to `status=merged` with `merged_into_id` pointing to the primary topic

#### Scenario: Topic hierarchy via parent-child relationships

- **WHEN** the KB compiler detects a hierarchical relationship (e.g., "RAG" is a subtopic of "LLM Architectures")
- **THEN** the child topic SHALL have `parent_topic_id` set to the parent topic's ID
- **AND** the parent topic article SHALL reference its child topics

### Requirement: Hierarchical TopicCategory taxonomy

The system SHALL store topic categories in a dedicated `topic_categories` table, replacing the fixed `ThemeCategory` enum for topic categorization. Each category SHALL have a unique `slug`, a display `name`, an optional `parent_id` (self-referential FK for hierarchy), and optional `description`, `icon`, `color`, and `display_order` fields. The table SHALL be seeded with the 8 existing ThemeCategory values as top-level categories. New categories SHALL be addable via API/CLI without database migrations.

#### Scenario: Default categories seeded from ThemeCategory enum

- **WHEN** the Alembic migration runs
- **THEN** the `topic_categories` table SHALL be seeded with 8 top-level records matching existing `ThemeCategory` values: ml_ai, devops_infra, data_engineering, business_strategy, tools_products, research_academia, security, other
- **AND** each seeded record SHALL have `parent_id=NULL` (top-level)

#### Scenario: Subcategory created via API

- **WHEN** `POST /api/v1/kb/categories` is called with `{"name": "LLMs", "parent_slug": "ml-ai"}`
- **THEN** a `TopicCategory` record SHALL be created with `parent_id` set to the `ml-ai` category's ID
- **AND** the response SHALL include the full category path (e.g., "ML/AI > LLMs")

#### Scenario: Category hierarchy maps to Obsidian folders

- **WHEN** the Obsidian export runs
- **THEN** each TopicCategory SHALL map to a directory in the vault
- **AND** subcategories SHALL be nested directories (e.g., `ML-AI/LLMs/Fine-tuning/`)
- **AND** topics SHALL be placed in their category's directory

#### Scenario: Topic references category by FK

- **WHEN** a Topic is created
- **THEN** its `category_id` SHALL be a foreign key to `topic_categories.id`
- **AND** the category SHALL be loadable via SQLAlchemy relationship

#### Scenario: Category listing via API

- **WHEN** `GET /api/v1/kb/categories` is called
- **THEN** the response SHALL be a tree-structured JSON with nested children
- **AND** each node SHALL include `slug`, `name`, `parent_slug`, `topic_count`, and `children`

### Requirement: TopicNote annotations on topics

The system SHALL support annotations on topics via a `topic_notes` table. Each note SHALL have a `topic_id` (foreign key), `note_type` (observation, question, correction, insight), `content` (text), `author` (system, agent:<persona>, or user), and `filed_back` (boolean indicating whether the note content was incorporated into the topic article).

#### Scenario: Agent files Q&A answer as TopicNote

- **WHEN** the KB Q&A agent answers a question about a topic with `--file-back` enabled
- **THEN** a `TopicNote` record SHALL be created with `note_type=insight`, `author=agent:<persona>`, and `filed_back=false`
- **AND** the next compilation cycle SHALL consider this note as evidence and set `filed_back=true` after incorporation

#### Scenario: User adds manual note

- **WHEN** a user submits a note via `POST /api/v1/kb/topics/:slug/notes`
- **THEN** a `TopicNote` record SHALL be created with `author=user`
- **AND** the note SHALL appear in the topic's notes list ordered by `created_at` descending

### Requirement: Incremental KB compilation

The KB compiler SHALL incrementally update topics based on new evidence since the last compilation. It SHALL NOT recompile all topics on every run. Full recompilation SHALL only occur when explicitly requested via `--full` flag.

#### Scenario: Incremental compile processes only new evidence

- **WHEN** `aca kb compile` is run without `--full`
- **THEN** the compiler SHALL only process `ThemeAnalysis` records created since the most recent `Topic.last_compiled_at` timestamp
- **AND** only topics with new evidence SHALL have their articles recompiled

#### Scenario: Full recompile regenerates all articles

- **WHEN** `aca kb compile --full` is run
- **THEN** ALL active and draft topics SHALL have their articles regenerated from all available evidence
- **AND** `article_version` SHALL be incremented for each recompiled topic

#### Scenario: Topic matching uses exact name then semantic similarity

- **WHEN** the compiler encounters a theme name from ThemeAnalysis
- **THEN** it SHALL first attempt exact name match against existing topics
- **AND** if no exact match, it SHALL compute embedding similarity against existing topic names
- **AND** if similarity exceeds the configured threshold (default 0.85), it SHALL update the matched topic
- **AND** if no match at all, it SHALL create a new topic with `status=draft`

#### Scenario: Compilation updates inter-topic relationships

- **WHEN** topics are compiled
- **THEN** the compiler SHALL detect related topics via co-occurrence in content and semantic similarity
- **AND** update `related_topic_ids` on affected topics
- **AND** sync relationships to the knowledge graph via `GraphitiClient` (backend-agnostic — supports both Neo4j and FalkorDB)

### Requirement: Auto-maintained KB indices stored as cached markdown

The system SHALL generate and maintain index files as special `Topic` records with slugs prefixed by `_`. These indices SHALL be regenerated after each compilation cycle.

#### Scenario: Master index generated

- **WHEN** compilation completes
- **THEN** a Topic record with `slug=_index` SHALL exist containing a markdown document listing all active topics with their 1-line summaries, grouped alphabetically
- **AND** this record SHALL have `status=active` and `category=OTHER`

#### Scenario: Category index generated

- **WHEN** compilation completes
- **THEN** a Topic record with `slug=_by_category` SHALL exist containing topics grouped by `ThemeCategory`
- **AND** each category section SHALL list topics with their trend classification and mention count

#### Scenario: Trend index generated

- **WHEN** compilation completes
- **THEN** a Topic record with `slug=_by_trend` SHALL exist containing topics grouped by `ThemeTrend` (emerging, growing, established, declining)

#### Scenario: Relationship map generated

- **WHEN** compilation completes
- **THEN** a Topic record with `slug=_relationship_map` SHALL exist containing a topic adjacency list showing which topics are related to which

#### Scenario: Indices readable by LLM agents

- **WHEN** an LLM agent calls `get_kb_index()` or `get_topic("_index")`
- **THEN** the agent SHALL receive the cached markdown index content
- **AND** the agent can use this to navigate to specific topics without requiring search

### Requirement: KB compilation integrated into daily pipeline

The KB compilation step SHALL run automatically after theme analysis in the `aca pipeline daily` command. It SHALL also be triggerable on-demand via CLI and API.

#### Scenario: Pipeline includes KB compilation

- **WHEN** `aca pipeline daily` is run
- **THEN** after the theme analysis step completes, the KB compiler SHALL run incrementally
- **AND** pipeline output SHALL include KB compilation statistics (topics created, updated, total)

#### Scenario: Pipeline KB step skippable

- **WHEN** `aca pipeline daily --skip-kb` is run
- **THEN** the KB compilation step SHALL be skipped
- **AND** all other pipeline steps SHALL execute normally

#### Scenario: On-demand compilation via API

- **WHEN** `POST /api/v1/kb/compile` is called with optional `{"full": true, "topic_slug": "rag-architecture"}`
- **THEN** the compiler SHALL run as specified (incremental/full, all/specific topic)
- **AND** the response SHALL include compilation statistics

### Requirement: KnowledgeBase specialist agent for Q&A

The system SHALL provide a new KnowledgeBase specialist agent that answers questions against the compiled knowledge base. The agent SHALL navigate topics via indices, read topic articles, and synthesize answers. KB tools SHALL also be available to the Research specialist for cross-cutting queries.

#### Scenario: KB agent answers question using compiled topics

- **WHEN** a user submits a question via `aca kb query "What are the trade-offs between RAG and fine-tuning?"`
- **THEN** the KB agent SHALL read the master index to identify relevant topics
- **AND** read the relevant topic articles
- **AND** query the knowledge graph for relationships between identified topics
- **AND** return a synthesized markdown answer

#### Scenario: KB agent files answer back as TopicNote

- **WHEN** a question is answered with `--file-back` flag
- **THEN** the answer SHALL be stored as a `TopicNote` with `note_type=insight` on each relevant topic
- **AND** `filed_back` SHALL be `false` until the next compilation incorporates it

#### Scenario: Research specialist has access to KB tools

- **WHEN** the Research specialist agent is executing a task
- **THEN** it SHALL have access to `search_knowledge_base`, `get_topic`, and `get_kb_index` tools
- **AND** it can use these alongside its existing `search_content` and `query_knowledge_graph` tools

### Requirement: KB health checks and linting

The system SHALL provide health check capabilities that detect quality issues in the knowledge base and optionally auto-fix them.

#### Scenario: Stale topic detection

- **WHEN** `aca kb lint` is run
- **THEN** topics with no new evidence since `last_evidence_at` exceeding the staleness threshold (default 30 days) SHALL be flagged as stale
- **AND** `--fix` flag SHALL auto-transition them to `status=stale`

#### Scenario: Merge candidate detection

- **WHEN** `aca kb lint` is run
- **THEN** the system SHALL compute pairwise embedding similarity between topic names
- **AND** pairs exceeding the merge threshold (default 0.90) SHALL be reported as merge candidates
- **AND** `--fix` flag SHALL auto-merge the lower-mention-count topic into the higher one

#### Scenario: Coverage gap analysis

- **WHEN** `aca kb lint` is run
- **THEN** the system SHALL report categories with fewer than the minimum topic count (default 3) as coverage gaps
- **AND** generate the `_coverage_gaps` index with recommendations

#### Scenario: Health report output

- **WHEN** `aca kb lint` completes
- **THEN** it SHALL output a structured markdown report with sections: Stale Topics, Merge Candidates, Coverage Gaps, Quality Scores
- **AND** the report SHALL include actionable recommendations

### Requirement: CLI commands for knowledge base management

The `aca kb` command group SHALL provide full KB management via the CLI.

#### Scenario: List topics with filters

- **WHEN** `aca kb list --category ml_ai --trend emerging` is run
- **THEN** the output SHALL list matching topics with name, category, trend, mention_count, and last_compiled_at
- **AND** default sort SHALL be by relevance_score descending

#### Scenario: Show topic article

- **WHEN** `aca kb show rag-architecture` is run
- **THEN** the output SHALL display the full markdown article for the topic with that slug
- **AND** if the topic does not exist, it SHALL display an error message

#### Scenario: Show master index

- **WHEN** `aca kb index` is run
- **THEN** the output SHALL display the cached master index markdown

#### Scenario: Query the knowledge base

- **WHEN** `aca kb query "What is the latest on AI agents?"` is run
- **THEN** the KB Q&A agent SHALL process the query and return a markdown answer

### Requirement: API endpoints for knowledge base

The API SHALL provide RESTful endpoints under `/api/v1/kb/` for topic management, notes, compilation, indices, health checks, and Q&A.

#### Scenario: List topics via API

- **WHEN** `GET /api/v1/kb/topics?category=ml_ai&trend=emerging&limit=20&offset=0` is called
- **THEN** the response SHALL be a JSON array of topic summaries with `slug`, `name`, `category`, `trend`, `status`, `mention_count`, `relevance_score`, `last_compiled_at`
- **AND** pagination SHALL be supported via `limit` and `offset`

#### Scenario: Get topic detail via API

- **WHEN** `GET /api/v1/kb/topics/rag-architecture` is called
- **THEN** the response SHALL include the full topic record including `article_md`, `summary`, all score fields, `related_topic_ids`, and `source_content_ids`

#### Scenario: Create topic manually via API

- **WHEN** `POST /api/v1/kb/topics` is called with `{"name": "Custom Topic", "category": "ml_ai"}`
- **THEN** a topic SHALL be created with `status=draft`, auto-generated slug, and empty article
- **AND** the response SHALL include the created topic with its slug

#### Scenario: Get topic notes via API

- **WHEN** `GET /api/v1/kb/topics/rag-architecture/notes` is called
- **THEN** the response SHALL be a JSON array of notes ordered by `created_at` descending

#### Scenario: 404 for non-existent topic

- **WHEN** `GET /api/v1/kb/topics/nonexistent-slug` is called
- **THEN** the response SHALL be HTTP 404 with detail "Topic 'nonexistent-slug' not found"

### Requirement: MCP tools for knowledge base access

The MCP server SHALL expose tools for LLM agents to interact with the knowledge base: `search_knowledge_base`, `get_topic`, `update_topic`, `add_topic_note`, `get_kb_index`, and `compile_knowledge_base`.

#### Scenario: search_knowledge_base returns relevant topics

- **WHEN** an LLM agent calls `search_knowledge_base(query="RAG patterns", limit=5)`
- **THEN** the tool SHALL return a JSON list of matching topics with slug, name, summary, and relevance score
- **AND** results SHALL use the existing hybrid search infrastructure

#### Scenario: get_topic returns article content

- **WHEN** an LLM agent calls `get_topic(slug="rag-architecture")`
- **THEN** the tool SHALL return the full topic record including `article_md`

#### Scenario: add_topic_note files an observation

- **WHEN** an LLM agent calls `add_topic_note(slug="rag-architecture", note="New evidence suggests...", note_type="observation")`
- **THEN** a TopicNote SHALL be created with `author=system`
- **AND** the tool SHALL return confirmation with the note ID

#### Scenario: compile_knowledge_base triggers compilation

- **WHEN** an LLM agent calls `compile_knowledge_base(topic_slug="rag-architecture")`
- **THEN** the KB compiler SHALL run for the specified topic
- **AND** the tool SHALL return compilation statistics

### Requirement: Obsidian vault export with three integration modes

The system SHALL export the knowledge base as an Obsidian-compatible vault. Three integration modes SHALL be specified; Mode 2 (file export) SHALL be implemented in this change. The export SHALL generate a directory structure with one `.md` file per topic, organized by the TopicCategory hierarchy. Each topic file SHALL include YAML frontmatter and article body with wikilinks. Index files SHALL be included. All modes SHALL use identical frontmatter format and folder structure to ensure forward compatibility.

#### Mode 2: File Export (implemented in this change)

Writes `.md` files directly to a specified output directory. The user opens this directory as an Obsidian vault.

#### Mode 1: CLI-Driven Export (specified, deferred)

Uses the official Obsidian CLI (`obsidian create`, `obsidian append`, `obsidian property:set`) to write directly to a live vault. Obsidian indexes immediately — no app restart needed. Requires Obsidian 1.12+ with CLI enabled.

#### Mode 3: Headless Sync (specified, deferred)

Combines file export with `obsidian-headless` (official npm package) for server deployments. Writes to a local directory, then `obsidian-headless sync --continuous` syncs to Obsidian Sync cloud. User's desktop/mobile Obsidian pulls from Sync. Enables bidirectional sync: `obsidian read` detects user edits, `aca kb import --from-obsidian` syncs them back to the database.

#### Scenario: Export generates three-tier folder structure (Category → Topic → Source)

- **WHEN** `aca kb export --format obsidian --output ./vault` is run
- **THEN** the output directory SHALL contain top-level folders matching the TopicCategory hierarchy (e.g., `ML-AI/`, `DevOps-Infra/`)
- **AND** each topic SHALL be a subfolder within its category (e.g., `ML-AI/RAG-Architecture/`)
- **AND** each topic folder SHALL contain an `_overview.md` file with the LLM-compiled article
- **AND** within each topic folder, source publications SHALL be subfolders (e.g., `ML-AI/RAG-Architecture/The-Batch/`)
- **AND** each source subfolder SHALL contain summary extract files linking to the full summaries

#### Scenario: Topic _overview.md includes YAML frontmatter

- **WHEN** a topic is exported
- **THEN** the `_overview.md` file SHALL begin with YAML frontmatter containing:
  - `slug`, `name`, `category_path` (e.g., "ML/AI"), `trend`, `status`
  - `relevance_score`, `mention_count`, `article_version`
  - `sources` (list of source publication names contributing to this topic)
  - `first_evidence_at`, `last_evidence_at`, `last_compiled_at`
  - `tags` (derived from key_points and category)
- **AND** the frontmatter SHALL be followed by the `article_md` content

#### Scenario: Source extract files link to summaries

- **WHEN** a topic has evidence from a source publication
- **THEN** a summary extract file SHALL be created at `Category/Topic/Source/date-slug.md`
- **AND** the extract SHALL contain key points from the summary
- **AND** the extract SHALL include a wikilink `[[summaries/slug]]` to the full summary

#### Scenario: Summaries and content stubs in flat reference directories

- **WHEN** the export runs
- **THEN** a `summaries/` directory SHALL contain one `.md` file per summary with full summary markdown and a `[[content/slug]]` wikilink
- **AND** a `content/` directory SHALL contain stub `.md` files with title, date, publication, and the original source URL

#### Scenario: Related topics rendered as wikilinks between _overview files

- **WHEN** a topic has `related_topic_ids`
- **THEN** the `_overview.md` SHALL contain wikilinks to related topics' `_overview.md` files
- **AND** these wikilinks SHALL use relative paths resolvable within the vault

#### Scenario: Index files exported to vault root

- **WHEN** the export runs
- **THEN** the vault root SHALL contain `_index.md`, `_by_category.md`, `_by_trend.md`, and `_relationship_map.md`
- **AND** these SHALL contain the cached index markdown from the corresponding Topic records

#### Scenario: Export available via API as ZIP

- **WHEN** `GET /api/v1/kb/export/obsidian` is called
- **THEN** the response SHALL be a ZIP archive with `Content-Type: application/zip`
- **AND** the ZIP SHALL contain the complete vault directory structure including `summaries/` and `content/` directories

#### Scenario: Incremental export only includes changed topics

- **WHEN** `aca kb export --format obsidian --output ./vault --since 2026-04-01` is run
- **THEN** only topics with `updated_at` after the specified date SHALL have their folders regenerated
- **AND** existing unchanged topic folders SHALL NOT be overwritten
- **AND** the `summaries/` and `content/` directories SHALL only receive new/changed files

#### Scenario: CLI-driven export writes to live vault (Mode 1, deferred)

- **WHEN** `aca kb export --format obsidian --use-cli` is run with Obsidian 1.12+ CLI enabled
- **THEN** the system SHALL use `obsidian create name="{name}" content="{content}" vault="{vault}" silent` for new topics
- **AND** `obsidian property:set name="{key}" value="{value}" file="{name}"` for frontmatter updates
- **AND** Obsidian SHALL index the new notes immediately without app restart

#### Scenario: Headless sync for server deployment (Mode 3, deferred)

- **WHEN** the system runs on a server (e.g., Railway) with `obsidian-headless` installed
- **THEN** file export SHALL write to a configured vault directory
- **AND** `obsidian-headless sync --continuous` SHALL sync the vault to Obsidian Sync cloud
- **AND** user's desktop/mobile Obsidian SHALL receive updates via Obsidian Sync

#### Scenario: Bidirectional sync via Obsidian read (Mode 3, deferred)

- **WHEN** `aca kb import --from-obsidian <vault-path>` is run
- **THEN** the system SHALL read `.md` files from the vault directory
- **AND** parse YAML frontmatter to identify the topic by slug
- **AND** compare `article_md` content with the database version
- **AND** if the file has been modified, update the Topic record with the new content
- **AND** set the article's `author` metadata to indicate user-edited content

#### Scenario: Frontmatter format compatible across all modes

- **WHEN** any export mode generates a topic file
- **THEN** the YAML frontmatter SHALL include: `slug`, `name`, `category_path`, `trend`, `status`, `relevance_score`, `mention_count`, `article_version`, `first_evidence_at`, `last_evidence_at`, `last_compiled_at`, and `tags`
- **AND** this format SHALL be identical across Modes 1, 2, and 3

### Requirement: Graph backend abstraction for topic relationships

All topic relationship storage and retrieval SHALL use the `GraphitiClient` abstraction layer. The system SHALL NOT use direct Cypher, FalkorDB, or Neo4j-specific queries. This ensures compatibility with both Neo4j and FalkorDB backends.

#### Scenario: Topic relationships synced via GraphitiClient

- **WHEN** the KB compiler detects related topics
- **THEN** it SHALL call `GraphitiClient.add_episode()` with structured topic relationship data
- **AND** it SHALL NOT execute any direct database-specific queries

#### Scenario: Topic context retrieved via GraphitiClient

- **WHEN** the KB compiler or Q&A agent needs historical context for a topic
- **THEN** it SHALL call `GraphitiClient.search_related_concepts()` or `GraphitiClient.get_temporal_context()`
- **AND** the response SHALL be backend-agnostic (same format regardless of Neo4j or FalkorDB)
