# Architecture

## Technology Stack

- **Language**: Python 3.11+
- **Package Management**: uv
- **Databases**:
  - PostgreSQL + SQLAlchemy (structured data: contents, summaries, digests)
  - Graphiti + Neo4j or FalkorDB (knowledge graph: concepts, themes, temporal relationships)
- **Storage**:
  - **Database Providers**: Local PostgreSQL, Supabase (cloud), Neon (serverless/branching)
  - **Image Storage**: Local filesystem, AWS S3, Supabase Storage (S3-compatible)
- **Agent Frameworks**: Multi-framework approach for comparison
  - Claude SDK (Anthropic) - Primary
  - OpenAI SDK (Agents/Assistants API)
  - Google ADK (Agent Development Kit)
  - Microsoft Agent Framework (Semantic Kernel or AutoGen)
- **Ingestion**: Gmail API, feedparser (RSS/Podcasts), YouTube Data API, OpenAI Whisper (STT)
- **Task Queue**: PostgreSQL queue (`pgqueuer_jobs`) with async workers
- **Web**: FastAPI (APIs, web UI)
- **Testing**: pytest

## System Architecture

```
src/
  agents/           # Agent framework implementations
    base.py         # Abstract base classes
    claude/         # Claude SDK agents (primary)
    openai/         # OpenAI SDK agents
    google/         # Google ADK agents
    microsoft/      # MS Agent Framework agents
  ingestion/        # Content fetching and parsing
    gmail.py        # Gmail API integration
    rss.py          # RSS feed parser (Substack, etc.)
    youtube.py      # YouTube playlist/transcript ingestion
    podcast.py      # Podcast feed transcript ingestion
    files.py        # File upload processing
  models/           # Data models (Pydantic + SQLAlchemy)
    content.py      # Unified Content model (all content)
    summary.py      # Summary model
    digest.py       # Digest model
    theme.py        # ThemeAnalysis model
    document.py     # DocumentContent dataclass (parser output)
  parsers/          # Document parsing
    base.py         # DocumentParser interface
    markitdown_parser.py  # Office docs, HTML, audio
    docling_parser.py     # Advanced PDF parsing with OCR
    youtube_parser.py     # YouTube transcript parsing
    router.py       # Parser routing and fallback
  services/         # Business logic
    content_service.py    # Content CRUD and deduplication
  storage/          # Data persistence
    database.py     # PostgreSQL
    graphiti_client.py  # Graphiti MCP integration (Neo4j/FalkorDB via GraphDBProvider)
  processors/       # Core processing
    summarizer.py
    theme_analyzer.py
    digest_creator.py
    historical_context.py
  delivery/         # Output channels
    email.py
    tts_service.py  # Text-to-speech for podcasts
  utils/            # Shared utilities
    markdown.py     # Markdown parsing and rendering
    summary_markdown.py   # Summary markdown templates
    digest_markdown.py    # Digest markdown templates
    content_hash.py       # Content deduplication hashing
  tasks/            # Queue task handlers
  api/              # FastAPI app
  config/           # Configuration
    models.py       # Model registry and configuration
    settings.py     # Application settings
    model_registry.yaml  # Model definitions and provider configs
```

## Key Workflows

### Content Processing Pipeline

1. **Ingestion**: Fetch from Gmail/Substack/YouTube → Parse content → Store raw
2. **Summarization**: Individual content → Structured summary → Extract entities
3. **Knowledge Graph**: Store entities/relationships in Graphiti (concepts, temporal evolution)
4. **Theme Analysis**: Query Graphiti for common themes, trending topics, historical context
5. **Digest Generation**: Multi-audience formatting (CTO strategy + developer tactics)
6. **Delivery**: Email/web with daily/weekly schedules

### Knowledge Graph (Graphiti) Usage

The knowledge graph supports pluggable backends via `GraphDBProvider`. The default backend is Neo4j (local Docker or AuraDB cloud), with FalkorDB available as a lightweight alternative. FalkorDB is Redis-protocol-compatible and supports local Docker, cloud (Railway), and embedded (FalkorDB Lite) modes. The backend is selected via `GRAPHDB_PROVIDER` and `GRAPHDB_MODE` settings, with all graph operations abstracted behind the provider interface.

- **Entity Extraction**: Technical concepts, companies, products, people, methodologies
- **Relationship Tracking**: How topics relate, co-occurrence patterns
- **Temporal Analysis**: Track concept evolution over time, identify emerging trends
- **Historical Context**: "We first discussed X when...", "This relates to previous theme Y..."
- **Queries**: "What topics are related to RAG?", "How has AI regulation discussion evolved?"

### Agent Framework Pattern

Each framework implementation provides:
- Content summarization agent
- Theme analysis agent
- Digest generation agent
- Consistent interfaces for comparison

This enables **direct performance comparisons** across frameworks:
- API design differences
- Tool use patterns
- Orchestration approaches
- Performance (speed, quality, token usage)
- Cost implications

## Data Models

### Content
The Content model is the data model for all ingested content:

- **Source Types**: GMAIL, RSS, YOUTUBE, PODCAST, FILE_UPLOAD
- **Source Tracking**: source_id, source_url for deduplication
- **Parsed Content**: markdown_content (LLM-optimized)
- **Structured Data**: tables_json, links_json, metadata_json
- **Raw Storage**: raw_content, raw_format for re-parsing
- **Parser Info**: parser_used, parser_version
- **Deduplication**: content_hash (SHA-256 of normalized markdown), canonical_id (FK to canonical record)
- **Status Tracking**: status, error_message, ingested_at, parsed_at, processed_at

```python
class ContentSource(str, Enum):
    GMAIL = "gmail"
    RSS = "rss"
    YOUTUBE = "youtube"
    PODCAST = "podcast"
    FILE_UPLOAD = "file_upload"
```

### Summary
- Linked to Content via content_id
- **markdown_content**: Full summary as structured markdown
- **theme_tags**: Extracted theme tags for cross-referencing
- Structured extraction with key themes, insights, technical details
- Relevance scores (CTO, teams, individuals)
- Model and cost tracking

Note: `NewsletterSummary` is a backwards-compatible alias for `Summary`.

### ThemeAnalysis
- Cross-content theme detection
- Trend classification (emerging, growing, established)
- Historical context integration
- Relevance scoring

### Digest
- Multi-audience formatted output
- **markdown_content**: Complete digest as structured markdown
- **theme_tags**: Aggregated theme tags from summaries
- **source_content_ids**: List of Content IDs used in digest
- Strategic insights (CTO-level)
- Technical developments (practitioner-level)
- Emerging trends with historical context
- Actionable recommendations per role

## Markdown Format Conventions

All processed content uses markdown for LLM-optimized storage and rendering.

### Summary Markdown Structure
```markdown
# Content Summary: {title}

## Executive Summary
Brief 2-3 sentence overview for leadership.

## Key Themes
- **Theme 1**: Description
- **Theme 2**: Description

## Strategic Insights
CTO-level implications and recommendations.

## Technical Details
Developer-focused technical information.

## Actionable Items
- [ ] Action item 1
- [ ] Action item 2

## Relevance Scores
- **CTO**: 0.85
- **Engineering Teams**: 0.75
- **Individual Contributors**: 0.65
```

### Embedded Reference Patterns
Content can embed references to tables and images:

- `[TABLE:id]` - References a table from tables_json
- `[IMAGE:id]` - References an image (with optional params: `[IMAGE:id|video=xxx&t=123]`)
- `[CODE:id]` - References a code block

The `render_with_embeds()` utility replaces these with actual content.

## Ingestion Services

### Gmail Ingestion (`GmailContentIngestionService`)
- Uses Gmail API with OAuth2 credentials
- Filters by labels/sender for content detection
- Extracts HTML body → converts to markdown via `HtmlMarkdownConverter`
- Deduplicates by `source_id` (message ID)

### RSS Ingestion (`RSSContentIngestionService`)
- Processes feeds from `substack_feeds.txt` configuration
- Uses feedparser for Atom/RSS parsing
- **Timezone handling**: `published_parsed` returns UTC but as naive struct_time - always add `tzinfo=UTC`:
  ```python
  datetime(*entry.published_parsed[:6], tzinfo=UTC)  # Correct
  ```
- Supports `--after-date` filtering for incremental ingestion

### YouTube Ingestion (`YouTubeContentIngestionService`)
- Uses YouTube Data API (OAuth for private, API key for public playlists)
- Fetches video metadata and transcripts via `youtube-transcript-api`
- Generates timestamped markdown with deep links (`youtu.be/xxx?t=123`)
- Playlist config file: `youtube_playlists.txt` with `PLAYLIST_ID | description` format
- API key fallback: `settings.get_youtube_api_key()` returns YOUTUBE_API_KEY or falls back to GOOGLE_API_KEY

### Podcast Ingestion (`PodcastContentIngestionService`)
- Fetches podcast RSS feeds via feedparser
- **3-tier transcript extraction**:
  1. Feed-embedded: `<content:encoded>`, `<description>`, `<itunes:summary>` (if ≥ 500 chars)
  2. Linked page: Detects `/transcript` or `/show-notes` URLs in show notes
  3. Audio fallback: Downloads audio and transcribes via OpenAI Whisper (gated by `transcribe: true`)
- Deduplicates by `source_id=podcast:{episode_guid}`
- Stores `raw_format` per tier: `feed_transcript`, `linked_transcript`, or `audio_transcript`
- Source config: `sources.d/podcasts.yaml` with per-feed `transcribe`, `stt_provider`, `languages`

### File Upload Ingestion (`FileContentIngestionService`)
- Processes uploads via `ParserRouter` → stores as Content records
- SHA-256 file hash for deduplication, links duplicates to canonical record
- API endpoint: `POST /api/v1/documents/upload` (multipart form data)
- Size limits: `MAX_UPLOAD_SIZE_MB`, `DOCLING_MAX_FILE_SIZE_MB` settings

## Parser Ecosystem

### Parser Interface
All parsers implement `DocumentParser` interface from `src/parsers/base.py`:
- Input: File bytes or URL
- Output: `DocumentContent` with markdown_content, tables, metadata

### Parser Router
`ParserRouter` selects appropriate parser based on file format:
1. Checks file extension/MIME type
2. Routes to specialized parser (or default)
3. Fallback chain for resilience

### Available Parsers

| Parser | Formats | Use Case |
|--------|---------|----------|
| `MarkItDownParser` | Office docs, HTML, audio | Lightweight, fast (~50ms) |
| `DoclingParser` | PDF, complex layouts | OCR support, table extraction |
| `YouTubeParser` | YouTube URLs | Transcript with timestamps |

### HTML-to-Markdown Conversion
`HtmlMarkdownConverter` in `src/parsers/html_markdown.py`:
- Primary: Trafilatura extraction (~50ms) for academic-quality markdown
- Dual input: `url=` for RSS feeds, `html=` for Gmail
- Async-native: `await converter.convert()` in async contexts
- Quality validation: `validate_markdown_quality()` checks structure
- Batch processing: `batch_convert()` with semaphore limiting
- **Crawl4AI fallback**: For JavaScript-heavy pages where Trafilatura returns insufficient content
  - Local mode: `AsyncWebCrawler` in-process (requires `crawl4ai` optional dep + browser)
  - Remote mode: HTTP `POST /md` to Docker-hosted Crawl4AI server (port 11235)
  - Selection: `crawl4ai_server_url` set → remote; unset → local
  - Fail-safe: extraction failures never block content ingestion

## Processing Stages

### Stage 1: Ingestion
**Input**: Gmail messages, RSS feeds, YouTube playlists, uploaded files
**Output**: Content records with parsed markdown
**Technology**: Gmail API, feedparser, YouTube Data API, ParserRouter
**Services**:
- `GmailContentIngestionService` - Email ingestion
- `RSSContentIngestionService` - RSS/Atom feeds
- `YouTubeContentIngestionService` - YouTube transcripts with timestamps
- `PodcastContentIngestionService` - Podcast feed transcripts
- `FileContentIngestionService` - PDF, DOCX, PPTX, etc.

### Stage 2: Summarization
**Input**: Content markdown_content
**Output**: Summary with markdown_content and theme_tags
**Technology**: Claude Haiku (default), Pydantic validation
**Cost**: ~$0.01-0.02 per content item

### Stage 3: Knowledge Graph Population
**Input**: Content summaries
**Output**: Entities and relationships in Graphiti
**Technology**: Graphiti MCP, Neo4j or FalkorDB (via `GraphDBProvider`)
**Purpose**: Enable temporal analysis and historical context

### Stage 4: Theme Analysis
**Input**: Multiple summaries + Graphiti context
**Output**: Cross-cutting themes with trends and relevance
**Technology**: Claude Sonnet (default), Graphiti queries
**Cost**: ~$0.05-0.10 per analysis (5-10 content items)

### Stage 5: Digest Creation
**Input**: Theme analysis + historical context
**Output**: Multi-audience formatted digest
**Technology**: Claude Sonnet (default)
**Cost**: ~$0.10-0.15 per digest

### Stage 6: Delivery
**Input**: Completed digest
**Output**: Email, web view
**Technology**: SendGrid (email), FastAPI (web)

## Job Queue Architecture

The system uses a PostgreSQL-based job queue for reliable background processing with transactional guarantees. Jobs are stored in the `pgqueuer_jobs` table and claimed using `SELECT FOR UPDATE SKIP LOCKED` for safe concurrent processing.

### Architecture Diagram

```
                              ┌─────────────────────────────────────────┐
                              │           PostgreSQL Database           │
                              │  ┌─────────────────────────────────┐   │
                              │  │         pgqueuer_jobs           │   │
                              │  │  • id, entrypoint, payload      │   │
                              │  │  • status, priority, progress   │   │
                              │  │  • created_at, started_at       │   │
                              │  │  • retry_count, error           │   │
                              │  └─────────────────────────────────┘   │
                              └─────────────────┬───────────────────────┘
                                                │
                     ┌──────────────────────────┼──────────────────────────┐
                     │                          │                          │
              ┌──────┴──────┐           ┌───────┴───────┐          ┌───────┴───────┐
              │  Producers  │           │  Job Queue    │          │    Workers    │
              │             │           │  (PostgreSQL) │          │               │
              │ • API calls │──enqueue──│               │──dequeue─│ • Concurrent  │
              │ • CLI cmds  │           │ • SKIP LOCKED │          │   processing  │
              │ • Scheduler │           │ • Priority    │          │ • Graceful    │
              │             │           │ • LISTEN/     │          │   shutdown    │
              └─────────────┘           │   NOTIFY      │          └───────────────┘
                                        └───────────────┘
                                                │
                                    ┌───────────┴───────────┐
                                    │    Task Handlers      │
                                    │                       │
                                    │ • summarize_content   │
                                    │ • ingest_content      │
                                    │ • extract_url_content │
                                    │ • process_content     │
                                    │ • scan_newsletters    │
                                    └───────────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Producers** | API endpoints, CLI commands, and scheduled tasks that enqueue jobs via `src/queue/setup.py` |
| **Job Queue** | `pgqueuer_jobs` PostgreSQL table with `SELECT FOR UPDATE SKIP LOCKED` for reliable dequeue |
| **Workers** | Async loops that claim and execute jobs concurrently (`src/queue/worker.py`) |
| **Task Handlers** | Registered async functions that process specific job entrypoints |

### Worker Modes

The worker can run in two modes:

| Mode | How it starts | Use case |
|------|--------------|----------|
| **Embedded** (default) | Auto-starts inside FastAPI lifespan | Development, single-service deployment |
| **Standalone** | `aca worker start` | Scaled deployment, debugging |

**Embedded mode** runs the worker as an `asyncio.create_task()` inside the FastAPI lifespan. It starts automatically when the API server boots — no extra processes needed. Controlled by environment variables:

```bash
WORKER_ENABLED=true       # Enable embedded worker (default: true)
WORKER_CONCURRENCY=5      # Max concurrent tasks (default: 5, max: 20)
```

**Standalone mode** runs the worker as a separate process via the CLI. Useful for Railway deployments where you want a dedicated worker service, or for running additional workers alongside the embedded one:

```bash
aca worker start                    # Default concurrency (5)
aca worker start --concurrency 10   # Custom concurrency
```

**Running both simultaneously** is safe — `SELECT FOR UPDATE SKIP LOCKED` prevents double-claiming. Jobs are distributed non-deterministically, and combined concurrency is additive. To run only standalone workers, set `WORKER_ENABLED=false` on the API service.

### Job Lifecycle

```
QUEUED → IN_PROGRESS → COMPLETED
              │
              └──(error)──→ FAILED ──(retry)──→ QUEUED
```

### Job Claiming

The worker uses PostgreSQL's `SELECT FOR UPDATE SKIP LOCKED` pattern for safe concurrent job claiming:

```sql
UPDATE pgqueuer_jobs
SET status = 'in_progress', started_at = NOW()
WHERE id IN (
    SELECT id FROM pgqueuer_jobs
    WHERE status = 'queued' AND execute_after <= NOW()
    ORDER BY priority DESC, created_at ASC
    LIMIT $batch_size
    FOR UPDATE SKIP LOCKED
)
RETURNING id, entrypoint, payload
```

The worker also uses `LISTEN/NOTIFY` on the `pgqueuer` channel for immediate wakeup when new jobs are enqueued, falling back to polling every 5 seconds.

### Job Management

```bash
# List jobs with optional filters
aca jobs list
aca jobs list --status failed
aca jobs list --entrypoint summarize_content

# View job details
aca jobs show 123

# Retry failed jobs
aca jobs retry 123
aca jobs retry --failed  # Retry all failed

# Cleanup old completed jobs
aca jobs cleanup --older-than 30d
```

## Scalability Considerations

- **Database**: PostgreSQL with indexes on frequently queried fields (status, dates)
- **Job Queue**: PGQueuer with transactional guarantees and configurable concurrency
- **Async Processing**: PostgreSQL-based queue replaces Redis for job management
- **Knowledge Graph**: Neo4j or FalkorDB optimized for temporal queries (pluggable via `GraphDBProvider`)
- **Caching**: Redis for frequently accessed data
- **Provider Failover**: Automatic fallback across multiple LLM providers
- **Cost Control**: Configurable model selection per pipeline step

## API Endpoints

### Content API (`/api/v1/contents`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/contents` | List contents with pagination and filtering |
| GET | `/contents/{id}` | Get single content by ID |
| POST | `/contents` | Create content manually |
| DELETE | `/contents/{id}` | Delete content |
| GET | `/contents/stats` | Statistics by source type and status |
| GET | `/contents/{id}/duplicates` | Find duplicate content |
| POST | `/contents/{id}/merge/{duplicate_id}` | Merge duplicate records |
| POST | `/contents/ingest` | Trigger background ingestion |
| GET | `/contents/ingest/status/{task_id}` | SSE progress stream |

### Summary API (`/api/v1/summaries`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/summaries` | List summaries with pagination |
| GET | `/summaries/{id}` | Get summary detail with markdown_content |
| GET | `/summaries/by-content/{content_id}` | Get summary by content ID |
| POST | `/summaries/trigger` | Trigger summarization |
| GET | `/summaries/stats` | Summary statistics |

### Newsletter API (`/api/v1/newsletters`) - REMOVED
The legacy Newsletter API has been removed. Use the Content API instead.

### Document Upload API (`/api/v1/documents`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/documents/upload` | Upload and parse document |
| GET | `/documents/formats` | List supported formats |
| GET | `/documents/{id}` | Get document status |

### Sources API (`/api/v1/sources`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sources` | List configured sources with content counts |

## Content API Features

The Content API provides:

1. **Source Types**: Explicit `source_type` field (gmail, rss, youtube, podcast, file_upload)
2. **Markdown First**: `markdown_content` is primary, `raw_content` stored for re-parsing
3. **Deduplication**: Built-in via `content_hash` and `canonical_id`
4. **Richer Metadata**: `tables_json`, `links_json`, `metadata_json` for structured data
